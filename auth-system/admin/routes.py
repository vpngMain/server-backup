"""Admin web: přihlášení a CRUD uživatelů a poboček (pouze pro role=admin)."""
import os
import re
import logging
from functools import wraps
from sqlalchemy import func, delete, insert
from flask import Blueprint, request, redirect, url_for, session, flash, render_template

logger = logging.getLogger(__name__)
from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH, OBJEDNAVAC_ROLES
from models import db, User, Branch, Warehouse, UserAllowedApp, ROUTER_APP_CODES, user_branches

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _pin_valid(pin: str) -> bool:
    if not pin or not isinstance(pin, str):
        return False
    pin = pin.strip()
    return PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH and re.match(r"^\d+$", pin) is not None


def _admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin_user_id"):
            return redirect(url_for("admin.login"))
        user = User.query.get(session["admin_user_id"])
        if not user or not user.is_admin or not user.active:
            session.pop("admin_user_id", None)
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrapped


@admin_bp.route("/")
def index():
    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_user_id"):
        u = User.query.get(session["admin_user_id"])
        if u and u.is_admin and u.active:
            return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        if not username or not pin:
            flash("Zadejte jméno a PIN.", "error")
        else:
            user = User.find_by_username(username)
            if user and user.check_pin(pin) and user.is_admin:
                session["admin_user_id"] = user.id
                return redirect(url_for("admin.dashboard"))
            flash("Neplatné údaje nebo nemáte oprávnění admina.", "error")
    return render_template("admin_login.html")


def _logout_chain_base():
    """Základ URL (scheme + host) pro řetěz odhlášení."""
    url = os.environ.get("ROUTER_URL", "").strip().rstrip("/")
    if url:
        try:
            from urllib.parse import urlparse
            p = urlparse(url)
            return f"{p.scheme}://{p.hostname}"
        except Exception:
            pass
    try:
        from urllib.parse import urlparse
        p = urlparse(request.url_root)
        return f"{p.scheme}://{p.hostname}"
    except Exception:
        return "http://localhost"


def _logout_chain_next_url():
    """První krok řetězu po auth: Odběros logout s parametrem chain=1."""
    base = _logout_chain_base()
    return f"{base}:8081/logout?chain=1"


@admin_bp.route("/logout")
def logout():
    session.pop("admin_user_id", None)
    next_url = request.args.get("next", "").strip()
    if next_url and next_url.startswith("http"):
        return redirect(next_url)
    return redirect(_logout_chain_next_url())


@admin_bp.route("/dashboard")
@_admin_required
def dashboard():
    users = User.query.order_by(User.username).all()
    # Předpočítat názvy poboček; při chybě (chybějící tabulka user_branches) fallback na u.branch
    users_branches = []
    for u in users:
        try:
            branch_names = [b.name for b in u.branches.all()]
        except Exception as e:
            logger.warning("dashboard: u.branches.all() selhalo pro user %s: %s", u.username, e)
            branch_names = [u.branch] if (getattr(u, "branch", None) and u.branch) else []
        users_branches.append((u, branch_names))
    return render_template("admin_dashboard.html", users_branches=users_branches, objednavac_roles=OBJEDNAVAC_ROLES)


def _user_branch_ids(user):
    if not user:
        return []
    try:
        return [b.id for b in user.branches]
    except Exception as e:
        logger.warning("_user_branch_ids selhalo pro user %s: %s", user.username if user else None, e)
        return []


def _user_allowed_app_codes(user):
    """Seznam kódů aplikací povolených na směrovači pro tohoto uživatele."""
    if not user:
        return []
    try:
        return [a.app_code for a in user.allowed_app_codes.all()]
    except Exception:
        return list(ROUTER_APP_CODES)


def _save_user_allowed_apps(user, app_codes):
    """Nastaví povolené aplikace na směrovači pro uživatele (kódy se ukládají lowercase)."""
    UserAllowedApp.query.filter_by(user_id=user.id).delete()
    codes_lower = {c.lower() for c in ROUTER_APP_CODES}
    for raw in app_codes:
        code = (raw or "").strip().lower()
        if code in codes_lower:
            db.session.add(UserAllowedApp(user_id=user.id, app_code=code))


def _set_user_branches_explicit(user_id, branch_ids):
    """Zapíše přiřazení poboček přímo do tabulky user_branches (spolehlivější než relationship)."""
    try:
        db.session.execute(delete(user_branches).where(user_branches.c.user_id == user_id))
        for bid in branch_ids:
            if Branch.query.get(bid):
                db.session.execute(insert(user_branches).values(user_id=user_id, branch_id=bid))
    except Exception as e:
        logger.warning("_set_user_branches_explicit: %s", e)


@admin_bp.route("/user/add", methods=["GET", "POST"])
@_admin_required
def user_add():
    all_branches = Branch.query.order_by(Branch.name).all()
    all_warehouses = Warehouse.query.order_by(Warehouse.name).all()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip()
        branch_ids = request.form.getlist("branch_ids", type=int)
        allowed_apps = request.form.getlist("allowed_apps")
        active = request.form.get("active") == "1"
        objednavac_role = (request.form.get("objednavac_role") or "").strip() or None
        warehouse = (request.form.get("warehouse") or "").strip() or None
        if not username:
            flash("Uživatelské jméno je povinné.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=[], router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=[])
        if not _pin_valid(pin):
            flash(f"PIN musí být {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} číslic.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=[], router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=[])
        if User.find_by_username(username, active_only=False):
            flash("Uživatel s tímto jménem již existuje.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=[], router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=[])
        user = User(username=username, role=role, branch=None, active=active, objednavac_role=objednavac_role, warehouse=warehouse)
        user.set_pin(pin)
        db.session.add(user)
        db.session.flush()
        _set_user_branches_explicit(user.id, branch_ids)
        first_b = Branch.query.get(branch_ids[0]) if branch_ids else None
        user.branch = first_b.name if first_b else None
        _save_user_allowed_apps(user, allowed_apps)
        db.session.commit()
        flash("Uživatel byl přidán.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, user_branch_ids=[], router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=list(ROUTER_APP_CODES))


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@_admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    all_branches = Branch.query.order_by(Branch.name).all()
    all_warehouses = Warehouse.query.order_by(Warehouse.name).all()
    user_branch_ids = _user_branch_ids(user)
    user_allowed = _user_allowed_app_codes(user)
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip()
        branch_ids = request.form.getlist("branch_ids", type=int)
        allowed_apps = request.form.getlist("allowed_apps")
        active = request.form.get("active") == "1"
        objednavac_role = (request.form.get("objednavac_role") or "").strip() or None
        warehouse = (request.form.get("warehouse") or "").strip() or None
        if not username:
            flash("Uživatelské jméno je povinné.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=user_branch_ids, router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=user_allowed)
        other = User.query.filter(func.lower(User.username) == username.strip().lower(), User.id != user.id).first()
        if other:
            flash("Uživatel s tímto jménem již existuje.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=user_branch_ids, router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=user_allowed)
        if pin and not _pin_valid(pin):
            flash(f"PIN musí být {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} číslic.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=user_branch_ids, router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=user_allowed)
        user.username = username
        user.role = role
        user.active = active
        user.objednavac_role = objednavac_role
        user.warehouse = warehouse
        if pin:
            user.set_pin(pin)
        _set_user_branches_explicit(user.id, branch_ids)
        first_b = Branch.query.get(branch_ids[0]) if branch_ids else None
        user.branch = first_b.name if first_b else None
        _save_user_allowed_apps(user, allowed_apps)
        db.session.commit()
        flash("Uživatel byl uložen.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES, all_branches=all_branches, all_warehouses=all_warehouses, user_branch_ids=user_branch_ids, router_app_codes=ROUTER_APP_CODES, user_allowed_app_codes=user_allowed)


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@_admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"Uživatel {username} byl smazán.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------- Pobočky ----------
@admin_bp.route("/branches")
@_admin_required
def branches():
    branches_list = Branch.query.order_by(Branch.name).all()
    return render_template("admin_branches.html", branches=branches_list)


@admin_bp.route("/branch/add", methods=["GET", "POST"])
@_admin_required
def branch_add():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip() or None
        if not name:
            flash("Název pobočky je povinný.", "error")
            return redirect(url_for("admin.branch_add"))
        if Branch.query.filter_by(name=name).first():
            flash("Pobočka s tímto názvem již existuje.", "error")
            return redirect(url_for("admin.branch_add"))
        b = Branch(name=name, code=code or "")
        db.session.add(b)
        db.session.commit()
        flash("Pobočka byla přidána.", "success")
        return redirect(url_for("admin.branches"))
    return render_template("admin_branch_form.html", branch=None)


@admin_bp.route("/branch/<int:branch_id>/edit", methods=["GET", "POST"])
@_admin_required
def branch_edit(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip() or None
        if not name:
            flash("Název pobočky je povinný.", "error")
            return render_template("admin_branch_form.html", branch=branch)
        other = Branch.query.filter(Branch.name == name, Branch.id != branch_id).first()
        if other:
            flash("Pobočka s tímto názvem již existuje.", "error")
            return render_template("admin_branch_form.html", branch=branch)
        branch.name = name
        branch.code = code or ""
        db.session.commit()
        flash("Pobočka byla uložena.", "success")
        return redirect(url_for("admin.branches"))
    return render_template("admin_branch_form.html", branch=branch)


@admin_bp.route("/branch/<int:branch_id>/delete", methods=["POST"])
@_admin_required
def branch_delete(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    name = branch.name
    db.session.delete(branch)
    db.session.commit()
    flash(f"Pobočka {name} byla smazána.", "success")
    return redirect(url_for("admin.branches"))


# ---------- Sklady ----------
@admin_bp.route("/warehouses")
@_admin_required
def warehouses():
    warehouses_list = Warehouse.query.order_by(Warehouse.name).all()
    return render_template("admin_warehouses.html", warehouses=warehouses_list)


@admin_bp.route("/warehouse/add", methods=["GET", "POST"])
@_admin_required
def warehouse_add():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip() or None
        if not name:
            flash("Název skladu je povinný.", "error")
            return redirect(url_for("admin.warehouse_add"))
        if Warehouse.query.filter_by(name=name).first():
            flash("Sklad s tímto názvem již existuje.", "error")
            return redirect(url_for("admin.warehouse_add"))
        w = Warehouse(name=name, code=code or "")
        db.session.add(w)
        db.session.commit()
        flash("Sklad byl přidán.", "success")
        return redirect(url_for("admin.warehouses"))
    return render_template("admin_warehouse_form.html", warehouse=None)


@admin_bp.route("/warehouse/<int:warehouse_id>/edit", methods=["GET", "POST"])
@_admin_required
def warehouse_edit(warehouse_id):
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip() or None
        if not name:
            flash("Název skladu je povinný.", "error")
            return render_template("admin_warehouse_form.html", warehouse=warehouse)
        other = Warehouse.query.filter(Warehouse.name == name, Warehouse.id != warehouse_id).first()
        if other:
            flash("Sklad s tímto názvem již existuje.", "error")
            return render_template("admin_warehouse_form.html", warehouse=warehouse)
        warehouse.name = name
        warehouse.code = code or ""
        db.session.commit()
        flash("Sklad byl uložen.", "success")
        return redirect(url_for("admin.warehouses"))
    return render_template("admin_warehouse_form.html", warehouse=warehouse)


@admin_bp.route("/warehouse/<int:warehouse_id>/delete", methods=["POST"])
@_admin_required
def warehouse_delete(warehouse_id):
    warehouse = Warehouse.query.get_or_404(warehouse_id)
    name = warehouse.name
    db.session.delete(warehouse)
    db.session.commit()
    flash(f"Sklad {name} byl smazán.", "success")
    return redirect(url_for("admin.warehouses"))