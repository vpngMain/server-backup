"""Admin web: přihlášení a CRUD uživatelů (pouze pro role=admin)."""
import re
from functools import wraps
from flask import Blueprint, request, redirect, url_for, session, flash, render_template
from config import PIN_MIN_LENGTH, PIN_MAX_LENGTH, OBJEDNAVAC_ROLES
from models import db, User

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
            user = User.query.filter_by(username=username, active=True).first()
            if user and user.check_pin(pin) and user.is_admin:
                session["admin_user_id"] = user.id
                session.permanent = True
                return redirect(url_for("admin.dashboard"))
            flash("Neplatné údaje nebo nemáte oprávnění admina.", "error")
    return render_template("admin_login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_user_id", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/dashboard")
@_admin_required
def dashboard():
    users = User.query.order_by(User.username).all()
    return render_template("admin_dashboard.html", users=users, objednavac_roles=OBJEDNAVAC_ROLES)


@admin_bp.route("/user/add", methods=["GET", "POST"])
@_admin_required
def user_add():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip()
        branch = (request.form.get("branch") or "").strip() or None
        active = request.form.get("active") == "1"
        objednavac_role = (request.form.get("objednavac_role") or "").strip() or None
        warehouse = (request.form.get("warehouse") or "").strip() or None
        if not username:
            flash("Uživatelské jméno je povinné.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES)
        if not _pin_valid(pin):
            flash(f"PIN musí být {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} číslic.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES)
        if User.query.filter_by(username=username).first():
            flash("Uživatel s tímto jménem již existuje.", "error")
            return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES)
        user = User(username=username, role=role, branch=branch, active=active, objednavac_role=objednavac_role, warehouse=warehouse)
        user.set_pin(pin)
        db.session.add(user)
        db.session.commit()
        flash("Uživatel byl přidán.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_user_form.html", user=None, objednavac_roles=OBJEDNAVAC_ROLES)


@admin_bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@_admin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip()
        branch = (request.form.get("branch") or "").strip() or None
        active = request.form.get("active") == "1"
        objednavac_role = (request.form.get("objednavac_role") or "").strip() or None
        warehouse = (request.form.get("warehouse") or "").strip() or None
        if not username:
            flash("Uživatelské jméno je povinné.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES)
        other = User.query.filter(User.username == username, User.id != user.id).first()
        if other:
            flash("Uživatel s tímto jménem již existuje.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES)
        if pin and not _pin_valid(pin):
            flash(f"PIN musí být {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} číslic.", "error")
            return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES)
        user.username = username
        user.role = role
        user.branch = branch
        user.active = active
        user.objednavac_role = objednavac_role
        user.warehouse = warehouse
        if pin:
            user.set_pin(pin)
        db.session.commit()
        flash("Uživatel byl uložen.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_user_form.html", user=user, objednavac_roles=OBJEDNAVAC_ROLES)


@admin_bp.route("/user/<int:user_id>/delete", methods=["POST"])
@_admin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"Uživatel {username} byl smazán.", "success")
    return redirect(url_for("admin.dashboard"))