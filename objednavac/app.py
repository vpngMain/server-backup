import os
import json
import threading
import requests
from functools import wraps
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    jsonify,
)
import click
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-in-production")
if os.environ.get("TESTING"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("TEST_DATABASE_URI", "sqlite:///:memory:")
    app.config["TESTING"] = True
else:
    _db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warehouse.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.abspath(_db_path).replace("\\", "/")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["APP_NAME"] = os.environ.get("APP_NAME", "Objednávač")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)


def _ensure_warehouse_note_column():
    """Přidá sloupec warehouse_note do order_items, pokud chybí (migrace pro existující DB)."""
    if getattr(_ensure_warehouse_note_column, "_done", False):
        return
    _ensure_warehouse_note_column._done = True
    try:
        from sqlalchemy import text
        db.session.execute(text("ALTER TABLE order_items ADD COLUMN warehouse_note TEXT"))
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.before_request
def _run_migrations():
    _ensure_warehouse_note_column()


ROLES = ("admin", "branch", "warehouse")
ORDER_STATUSES = ("pending", "shipped", "partially_shipped")
STATUS_CZ = {
    "pending": "Čeká",
    "processed": "Zpracováno",  # jen pro zobrazení starých záznamů
    "shipped": "Odesláno",
    "partially_shipped": "Částečně odesláno",
}


user_branches = db.Table(
    "user_branches",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("branch_id", db.Integer, db.ForeignKey("branches.id"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)  # výchozí / zpětná kompatibilita
    branch = db.relationship("Branch", backref="users", foreign_keys=[branch_id])
    branches = db.relationship("Branch", secondary=user_branches, backref=db.backref("branch_users", lazy="dynamic"), lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_branch_ids(self):
        """Seznam ID poboček, k nimž je uživatel přiřazen (včetně branch_id pro zpětnou kompatibilitu)."""
        ids = []
        if self.branch_id:
            ids.append(self.branch_id)
        for b in self.branches:
            if b.id not in ids:
                ids.append(b.id)
        return ids

    def has_any_branch(self):
        return bool(self.branch_id or self.branches.count() > 0)

    def branch_names_display(self):
        """Pro zobrazení v adminu: názvy poboček oddělené čárkou."""
        ids = self.get_branch_ids()
        if not ids:
            return "—"
        names = [Branch.query.get(bid).name for bid in ids if Branch.query.get(bid)]
        return ", ".join(names) if names else "—"


class Branch(db.Model):
    __tablename__ = "branches"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), nullable=True)
    orders = db.relationship("Order", backref="branch", lazy="dynamic")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), nullable=True)           # kód produktu (volitelný)
    unit = db.Column(db.String(50), nullable=True)          # jednotka: ks, ml, balení atd.
    group_name = db.Column(db.String(255), nullable=True)   # název_skupiny z importu
    pc = db.Column(db.String(100), nullable=True)            # sloupec pc z importu
    is_internal = db.Column(db.Boolean, default=False, nullable=False)  # kancelář / interní objednávky (legacy; nově používat InternalProduct)


class InternalProduct(db.Model):
    """Samostatná tabulka interních produktů (kancelář) – oddělená od běžných produktů."""
    __tablename__ = "internal_products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    group_name = db.Column(db.String(255), nullable=True)
    pc = db.Column(db.String(100), nullable=True)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    invoice_ok = db.Column(db.Boolean, nullable=True)
    invoice_note = db.Column(db.Text, nullable=True)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    order_type = db.Column(db.String(30), default="normal", nullable=False)
    created_by_warehouse_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_warehouse = db.relationship("User", foreign_keys=[created_by_warehouse_id])


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)   # běžné objednávky; u interních se použije placeholder
    internal_product_id = db.Column(db.Integer, db.ForeignKey("internal_products.id"), nullable=True)  # interní objednávky
    ordered_quantity = db.Column(db.Float, nullable=False)
    shipped_quantity = db.Column(db.Float, nullable=True)
    branch_note = db.Column(db.String(255), nullable=True)
    warehouse_note = db.Column(db.Text, nullable=True)  # poznámka skladu k položce
    custom_product_name = db.Column(db.String(255), nullable=True)  # název produktu, když není v DB
    unavailable = db.Column(db.Boolean, default=False, nullable=False)
    product = db.relationship("Product", backref="order_items")
    internal_product = db.relationship("InternalProduct", backref="order_items")

    def display_name(self):
        if self.internal_product:
            return self.internal_product.name
        return self.custom_product_name or (self.product.name if self.product else "—")


class BranchCart(db.Model):
    """Trvalý košík pro uživatele a pobočku – synchronizace mezi zařízeními. Interní košík zvlášť."""
    __tablename__ = "branch_carts"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), primary_key=True)
    cart_json = db.Column(db.Text, nullable=False, default="{}")
    cart_internal_json = db.Column(db.Text, nullable=False, default="{}")
    notes_json = db.Column(db.Text, nullable=False, default="{}")
    custom_json = db.Column(db.Text, nullable=False, default="[]")


class AuditLog(db.Model):
    """Log změn pro audit (kdo, kdy, co)."""
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    user = db.relationship("User", backref="audit_logs")


def notify_worker(order_id, branch_name):
    # --- NASTAVENÍ ---
    TOKEN = "8308981650:AAE9ruZxe9lZuMZFM24eEng1UuxwFKem4w4"
    CHAT_ID = "-1003891440639"
    # -----------------

    # Sestavení krátké zprávy
    cas = datetime.now().strftime('%H:%M:%S')
    message = (
        f"🔔 *Nová objednávka!*\n"
        f"🏢 Pobočka: *{branch_name}*\n"
        f"🕒 Čas: {cas}\n"
        f"🆔 ID: #{order_id}"
    )

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return inner


def role_required(*allowed):
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = User.query.get(session["user_id"])
            effective = user.role if user else None
            if user and user.role == "admin" and session.get("acting_as_role") in allowed:
                effective = session.get("acting_as_role")
            if not user or effective not in allowed:
                flash("Přístup odepřen.", "error")
                if user and user.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                if user and user.role == "warehouse":
                    return redirect(url_for("warehouse_dashboard"))
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return inner
    return decorator


def get_current_user():
    if "user_id" not in session:
        return None
    return User.query.get(session["user_id"])


def get_current_branch_id():
    """Vrátí ID pobočky, pro kterou uživatel právě objednává (session nebo výchozí). Admin v režimu pobočky používá acting_as_branch_id."""
    user = get_current_user()
    if user and user.role == "admin" and session.get("acting_as_role") == "branch":
        bid = session.get("acting_as_branch_id")
        if bid is not None and Branch.query.get(bid):
            return int(bid)
        return None
    if not user or user.role != "branch":
        return None
    current = session.get("current_branch_id")
    if current is not None:
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = None
    if current and user.get_branch_ids() and current in user.get_branch_ids():
        return current
    ids = user.get_branch_ids()
    if ids:
        session["current_branch_id"] = ids[0]
        return ids[0]
    return user.branch_id


def status_cz(key):
    return STATUS_CZ.get(key, key)


def audit_log(action, entity_type=None, entity_id=None, details=None):
    """Zapíše záznam do audit logu. U admina v režimu pobočka/sklad přidá poznámku."""
    user = get_current_user()
    username = user.username if user else "anonymous"
    uid = user.id if user else None
    acting = session.get("acting_as_role")
    if user and user.role == "admin" and acting:
        suffix = f" [admin jako {acting}]"
        details = (details or "") + suffix
    try:
        log = AuditLog(
            user_id=uid,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.template_filter("format_datetime")
def format_datetime_filter(dt):
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


@app.template_filter("format_qty")
def format_qty_filter(value):
    """Zobrazí množství jako celé číslo, pokud je to celé (3.0 → 3)."""
    if value is None:
        return "—"
    try:
        f = float(value)
        if f == int(f):
            return str(int(f))
        return str(f)
    except (TypeError, ValueError):
        return str(value)


# Možnosti mg pro filtr (pořadí v UI)
PRODUCT_MG_OPTIONS = ["0mg", "3mg", "6mg", "10mg", "11mg", "12mg", "18mg", "20mg"]
# Pořadí při detekci v názvu (od nejdelšího, aby "20mg" neodpovídalo jako "0mg")
PRODUCT_MG_DETECT_ORDER = ["20mg", "18mg", "12mg", "11mg", "10mg", "6mg", "3mg", "0mg"]


def _product_category(name):
    """Z názvu produktu extrahuje mg (0mg, 3mg, 6mg, 10mg, 20mg) pro filtrování a označení."""
    if not name or not isinstance(name, str):
        return None
    n = name.lower()
    for mg in PRODUCT_MG_DETECT_ORDER:
        if mg in n:
            return mg
    return None


@app.template_filter("product_category")
def product_category_filter(name):
    """Template filter: vrátí '0mg', '3mg', '6mg', '10mg', '20mg' nebo prázdný řetězec."""
    cat = _product_category(name)
    return cat if cat else ""


def _get_branches_for_current_user():
    """Pobočky, k nimž je přihlášený uživatel (branch) přiřazen – pro výběr pobočky. Admin v režimu pobočky vidí jen tu jednu."""
    user = get_current_user()
    if user and user.role == "admin" and session.get("acting_as_role") == "branch":
        bid = session.get("acting_as_branch_id")
        if bid and Branch.query.get(bid):
            return [Branch.query.get(bid)]
        return []
    if not user or user.role != "branch":
        return []
    ids = user.get_branch_ids()
    if not ids:
        return []
    return Branch.query.filter(Branch.id.in_(ids)).order_by(Branch.name).all()


@app.context_processor
def inject_user():
    current = get_current_user()
    acting_as_role = session.get("acting_as_role") if current and current.role == "admin" else None
    acting_as_branch = None
    if acting_as_role == "branch" and session.get("acting_as_branch_id"):
        acting_as_branch = Branch.query.get(session["acting_as_branch_id"])
    branch_list = _get_branches_for_current_user() if (current and (current.role == "branch" or acting_as_role == "branch")) else []
    current_branch_id = get_current_branch_id() if current else None
    current_branch = Branch.query.get(current_branch_id) if current_branch_id else None
    return {
        "current_user": current,
        "status_cz": status_cz,
        "current_branch": current_branch,
        "user_branches": branch_list,
        "acting_as_role": acting_as_role,
        "acting_as_branch": acting_as_branch,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session.pop("current_branch_id", None)
            if user.role == "branch":
                ids = user.get_branch_ids()
                if ids:
                    session["current_branch_id"] = ids[0]
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            if user.role == "warehouse":
                return redirect(url_for("warehouse_dashboard"))
            if user.role == "branch":
                return redirect(url_for("branch_dashboard"))
            return redirect(url_for("index"))
        flash("Neplatné přihlašovací údaje.", "error")
    return render_template("login.html")


@app.route("/branch/switch", methods=["POST"])
@login_required
@role_required("branch")
def branch_switch():
    branch_id = request.form.get("branch_id", type=int)
    user = get_current_user()
    if branch_id and user.get_branch_ids() and branch_id in user.get_branch_ids():
        session["current_branch_id"] = branch_id
        flash("Pobočka změněna.")
    return redirect(request.referrer or url_for("branch_dashboard"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("current_branch_id", None)
    session.pop("acting_as_role", None)
    session.pop("acting_as_branch_id", None)
    return redirect(url_for("login"))


def _load_branch_cart_from_db():
    """Načte košík z DB do session – vždy (běžný i interní)."""
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return
    row = BranchCart.query.filter_by(user_id=user.id, branch_id=bid).first()
    cart_by_branch = session.get("cart_by_branch", {})
    cart_internal_by_branch = session.get("cart_internal_by_branch", {})
    notes_by_branch = session.get("cart_branch_notes", {})
    custom_by_branch = session.get("cart_custom_by_branch", {})
    if row:
        try:
            cart_by_branch[str(bid)] = json.loads(row.cart_json) if row.cart_json else {}
            try:
                cart_internal_by_branch[str(bid)] = json.loads(row.cart_internal_json) if getattr(row, "cart_internal_json", None) else {}
            except (json.JSONDecodeError, TypeError, AttributeError):
                cart_internal_by_branch[str(bid)] = {}
            notes_by_branch[str(bid)] = json.loads(row.notes_json) if row.notes_json else {}
            custom_by_branch[str(bid)] = json.loads(row.custom_json) if row.custom_json else []
        except (json.JSONDecodeError, TypeError):
            cart_by_branch[str(bid)] = {}
            cart_internal_by_branch[str(bid)] = {}
            notes_by_branch[str(bid)] = {}
            custom_by_branch[str(bid)] = []
    else:
        cart_by_branch[str(bid)] = {}
        cart_internal_by_branch[str(bid)] = {}
        notes_by_branch[str(bid)] = {}
        custom_by_branch[str(bid)] = []
    session["cart_by_branch"] = cart_by_branch
    session["cart_internal_by_branch"] = cart_internal_by_branch
    session["cart_branch_notes"] = notes_by_branch
    session["cart_custom_by_branch"] = custom_by_branch


def _save_branch_cart_to_db():
    """Uloží aktuální košíky (běžný i interní) aktuální pobočky do DB."""
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return
    cart_by_branch = session.get("cart_by_branch", {})
    cart_internal_by_branch = session.get("cart_internal_by_branch", {})
    notes_by_branch = session.get("cart_branch_notes", {})
    custom_by_branch = session.get("cart_custom_by_branch", {})
    cart = cart_by_branch.get(str(bid), {})
    cart_internal = cart_internal_by_branch.get(str(bid), {})
    notes = notes_by_branch.get(str(bid), {})
    custom = custom_by_branch.get(str(bid), [])
    row = BranchCart.query.filter_by(user_id=user.id, branch_id=bid).first()
    if not row:
        row = BranchCart(user_id=user.id, branch_id=bid)
        db.session.add(row)
    row.cart_json = json.dumps(cart)
    if hasattr(row, "cart_internal_json"):
        row.cart_internal_json = json.dumps(cart_internal)
    row.notes_json = json.dumps(notes)
    row.custom_json = json.dumps(custom)
    db.session.commit()


def _get_branch_cart():
    """Košík podle order_type: běžný nebo interní. Načte z DB, pokud ještě nebyl načten."""
    bid = get_current_branch_id()
    if not bid:
        return {}
    _load_branch_cart_from_db()
    if session.get("order_type") == "internal":
        return session.get("cart_internal_by_branch", {}).get(str(bid), {})
    return session.get("cart_by_branch", {}).get(str(bid), {})


def _set_branch_cart(cart):
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return
    if session.get("order_type") == "internal":
        cart_internal_by_branch = session.get("cart_internal_by_branch", {})
        cart_internal_by_branch[str(bid)] = cart
        session["cart_internal_by_branch"] = cart_internal_by_branch
    else:
        cart_by_branch = session.get("cart_by_branch", {})
        cart_by_branch[str(bid)] = cart
        session["cart_by_branch"] = cart_by_branch
    _save_branch_cart_to_db()


def _get_branch_cart_notes():
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return {}
    notes = session.get("cart_branch_notes", {})
    return notes.get(str(bid), {})


def _set_branch_cart_notes(notes):
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return
    by_branch = session.get("cart_branch_notes", {})
    by_branch[str(bid)] = notes
    session["cart_branch_notes"] = by_branch
    _save_branch_cart_to_db()


def _get_branch_cart_custom():
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return []
    by_branch = session.get("cart_custom_by_branch", {})
    return by_branch.get(str(bid), [])


def _set_branch_cart_custom(items):
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        return
    by_branch = session.get("cart_custom_by_branch", {})
    by_branch[str(bid)] = items
    session["cart_custom_by_branch"] = by_branch
    _save_branch_cart_to_db()


@app.route("/branch")
@login_required
@role_required("branch")
def branch_dashboard():
    from sqlalchemy import func
    bid = get_current_branch_id()
    if not bid:
        return redirect(url_for("index"))
    branch = Branch.query.get(bid)
    if not branch:
        return redirect(url_for("index"))
    orders_q = Order.query.filter_by(branch_id=bid)
    total_orders = orders_q.count()
    by_status = (
        db.session.query(Order.status, func.count(Order.id))
        .filter(Order.branch_id == bid)
        .group_by(Order.status)
        .all()
    )
    status_counts = {s: c for s, c in by_status}
    recent_orders = Order.query.filter_by(branch_id=bid).order_by(Order.created_at.desc()).limit(10).all()
    last_order = Order.query.filter_by(branch_id=bid, order_type="normal").order_by(Order.created_at.desc()).first()
    last_order_unavailable = []
    if last_order:
        last_order_unavailable = [i for i in last_order.items if i.unavailable]
    return render_template(
        "branch_dashboard.html",
        user=get_current_user(),
        branch=branch,
        total_orders=total_orders,
        status_counts=status_counts,
        recent_orders=recent_orders,
        status_cz=status_cz,
        last_order=last_order,
        last_order_unavailable=last_order_unavailable,
    )


def _product_brand(name):
    """První slovo názvu = značka."""
    if not name or not name.strip():
        return ""
    return (name.strip().split() or [""])[0]


@app.route("/")
@login_required
@role_required("branch")
def index():
    """Běžné produkty (ne interní) – samostatná stránka."""
    from collections import defaultdict
    from sqlalchemy import or_
    session["order_type"] = "normal"
    user = get_current_user()
    q = request.args.get("q", "").strip()
    group_filter = request.args.get("group", "").strip() or None
    brand_filter = request.args.get("brand", "").strip() or None
    category_filter = request.args.get("category", "").strip() or None  # 10mg | 20mg
    base = Product.query.filter(
        Product.name != "[Vlastní – produkt mimo katalog]",
        db.or_(Product.is_internal == False, Product.is_internal.is_(None)),
    )
    if group_filter:
        base = base.filter(Product.group_name == group_filter)
    if q:
        q_like = f"%{q}%"
        products = base.filter(
            or_(Product.name.ilike(q_like), Product.sku.ilike(q_like))
        ).order_by(Product.name).all()
    else:
        products = base.order_by(Product.group_name, Product.name).all()
    brands = sorted({_product_brand(p.name) for p in products if _product_brand(p.name)})
    if brand_filter:
        products = [p for p in products if _product_brand(p.name) == brand_filter]
    if category_filter and category_filter in PRODUCT_MG_OPTIONS:
        products = [p for p in products if _product_category(p.name) == category_filter]
    groups = sorted({p.group_name for p in products if p.group_name})
    categories = PRODUCT_MG_OPTIONS.copy()
    by_brand = defaultdict(list)
    for p in products:
        by_brand[_product_brand(p.name) or "—"].append(p)
    products_by_brand = sorted(by_brand.items(), key=lambda x: x[0])
    cart = _get_branch_cart()
    cart_notes = _get_branch_cart_notes()
    return render_template(
        "products.html",
        products=products,
        products_by_brand=products_by_brand,
        cart=cart,
        cart_notes=cart_notes,
        user=user,
        search_q=q,
        groups=groups,
        group_filter=group_filter,
        brands=brands,
        brand_filter=brand_filter,
        categories=categories,
        category_filter=category_filter,
    )


@app.route("/internal")
@login_required
@role_required("branch")
def internal_products():
    """Interní produkty ze samostatné tabulky internal_products – oddělená stránka a databáze."""
    from collections import defaultdict
    from sqlalchemy import or_
    session["order_type"] = "internal"
    user = get_current_user()
    q = request.args.get("q", "").strip()
    group_filter = request.args.get("group", "").strip() or None
    brand_filter = request.args.get("brand", "").strip() or None
    base = InternalProduct.query
    if group_filter:
        base = base.filter(InternalProduct.group_name == group_filter)
    if q:
        q_like = f"%{q}%"
        products = base.filter(
            or_(InternalProduct.name.ilike(q_like), db.and_(InternalProduct.sku.isnot(None), InternalProduct.sku.ilike(q_like)))
        ).order_by(InternalProduct.name).all()
    else:
        products = base.order_by(InternalProduct.group_name, InternalProduct.name).all()
    brands = sorted({_product_brand(p.name) for p in products if _product_brand(p.name)})
    if brand_filter:
        products = [p for p in products if _product_brand(p.name) == brand_filter]
    groups = sorted({p.group_name for p in products if p.group_name})
    by_brand = defaultdict(list)
    for p in products:
        by_brand[_product_brand(p.name) or "—"].append(p)
    products_by_brand = sorted(by_brand.items(), key=lambda x: x[0])
    cart = _get_branch_cart()
    cart_notes = _get_branch_cart_notes()
    return render_template(
        "internal_products.html",
        products=products,
        products_by_brand=products_by_brand,
        cart=cart,
        cart_notes=cart_notes,
        user=user,
        search_q=q,
        groups=groups,
        group_filter=group_filter,
        brands=brands,
        brand_filter=brand_filter,
    )


def _get_or_create_custom_placeholder_product():
    p = Product.query.filter_by(name="[Vlastní – produkt mimo katalog]").first()
    if not p:
        p = Product(name="[Vlastní – produkt mimo katalog]", sku=None, unit="ks")
        db.session.add(p)
        db.session.flush()
    return p


def _redirect_back_to_products(product_id=None):
    """Přesměruje zpět na stránku produktů s původním hledáním (bez scrollu na řádek)."""
    from urllib.parse import urlparse, urlunparse
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        parsed = urlparse(referrer)
        if parsed.path.rstrip("/") in ("", "/") and "/cart" not in referrer:
            next_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
            return redirect(next_url)
    return redirect(url_for("index"))


@app.route("/cart/add-custom", methods=["POST"])
@login_required
@role_required("branch")
def cart_add_custom():
    name = request.form.get("custom_product_name", "").strip()
    quantity = request.form.get("quantity", type=float, default=1)
    if not name or quantity <= 0:
        flash("Zadejte název produktu a množství.", "error")
        return redirect(url_for("index"))
    custom = _get_branch_cart_custom()
    custom.append({"name": name, "quantity": quantity})
    _set_branch_cart_custom(custom)
    flash(f"Přidáno: {name} ({quantity} ks)")
    return _redirect_back_to_products()


@app.route("/cart/add", methods=["POST"])
@login_required
@role_required("branch")
def cart_add():
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=float, default=1)
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not product_id or quantity <= 0:
        if wants_json:
            return jsonify({"ok": False, "error": "Neplatné množství."}), 400
        flash("Neplatné množství.", "error")
        return redirect(url_for("index"))
    product = Product.query.get(product_id)
    if not product:
        if wants_json:
            return jsonify({"ok": False, "error": "Produkt nenalezen."}), 400
        flash("Produkt nenalezen.", "error")
        return redirect(url_for("index"))
    cart = _get_branch_cart()
    key = str(product_id)
    cart[key] = cart.get(key, 0) + quantity
    _set_branch_cart(cart)
    branch_note = request.form.get("branch_note", "").strip() or None
    notes = _get_branch_cart_notes()
    if branch_note:
        notes[key] = branch_note
    else:
        notes.pop(key, None)
    _set_branch_cart_notes(notes)
    if wants_json:
        return jsonify({"ok": True, "cart_qty": cart[key], "message": f"Přidáno: {product.name}"})
    return _redirect_back_to_products(product_id=product_id)


@app.route("/cart/add-internal", methods=["POST"])
@login_required
@role_required("branch")
def cart_add_internal():
    """Přidá interní produkt (z tabulky internal_products) do interního košíku."""
    session["order_type"] = "internal"
    internal_product_id = request.form.get("internal_product_id", type=int) or request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=float, default=1)
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not internal_product_id or quantity <= 0:
        if wants_json:
            return jsonify({"ok": False, "error": "Neplatné množství."}), 400
        flash("Neplatné množství.", "error")
        return redirect(url_for("internal_products"))
    ip = InternalProduct.query.get(internal_product_id)
    if not ip:
        if wants_json:
            return jsonify({"ok": False, "error": "Interní produkt nenalezen."}), 400
        flash("Interní produkt nenalezen.", "error")
        return redirect(url_for("internal_products"))
    cart = _get_branch_cart()
    key = str(internal_product_id)
    cart[key] = cart.get(key, 0) + quantity
    _set_branch_cart(cart)
    if wants_json:
        return jsonify({"ok": True, "cart_qty": cart[key], "message": f"Přidáno: {ip.name}"})
    flash(f"Přidáno: {ip.name} ({quantity} ks)")
    return redirect(request.referrer or url_for("internal_products"))


@app.route("/cart")
@login_required
@role_required("branch")
def cart_view():
    user = get_current_user()
    cart = _get_branch_cart()
    cart_notes = _get_branch_cart_notes()
    order_type = session.get("order_type", "normal")
    items = []
    if order_type == "internal":
        for pid_str, qty in cart.items():
            if qty <= 0:
                continue
            pid = int(pid_str)
            p = InternalProduct.query.get(pid)
            if p:
                items.append({
                    "product": p,
                    "quantity": qty,
                    "branch_note": cart_notes.get(pid_str, ""),
                    "is_custom": False,
                })
    else:
        for pid_str, qty in cart.items():
            if qty <= 0:
                continue
            pid = int(pid_str)
            p = Product.query.get(pid)
            if p:
                items.append({
                    "product": p,
                    "quantity": qty,
                    "branch_note": cart_notes.get(pid_str, ""),
                    "is_custom": False,
                })
        custom = _get_branch_cart_custom()
        for idx, c in enumerate(custom):
            if c.get("quantity", 0) <= 0:
                continue
            items.append({
                "product": None,
                "quantity": c["quantity"],
                "branch_note": "",
                "is_custom": True,
                "custom_name": c.get("name", ""),
                "custom_index": idx,
            })
    return render_template("cart.html", items=items, user=user, order_type=order_type)


@app.route("/cart/update", methods=["POST"])
@login_required
@role_required("branch")
def cart_update():
    cart = _get_branch_cart()
    notes = _get_branch_cart_notes()
    for key in list(cart.keys()):
        new_qty = request.form.get(f"qty_{key}", type=float)
        if new_qty is not None:
            if new_qty <= 0:
                cart.pop(key, None)
                notes.pop(key, None)
            else:
                cart[key] = new_qty
        note_val = request.form.get(f"note_{key}", "").strip() or None
        if key in cart:
            if note_val:
                notes[key] = note_val
            else:
                notes.pop(key, None)
    _set_branch_cart(cart)
    _set_branch_cart_notes(notes)
    if session.get("order_type") != "internal":
        custom = []
        idx = 0
        while idx < 500:
            name_val = request.form.get(f"custom_{idx}_name")
            if name_val is None:
                break
            name = name_val.strip()
            qty = request.form.get(f"custom_{idx}_qty", type=float)
            if name and qty is not None and qty > 0:
                custom.append({"name": name, "quantity": qty})
            idx += 1
        _set_branch_cart_custom(custom)
    return redirect(url_for("cart_view"))


@app.route("/cart/remove-custom/<int:index>", methods=["POST"])
@login_required
@role_required("branch")
def cart_remove_custom(index):
    custom = _get_branch_cart_custom()
    if 0 <= index < len(custom):
        custom.pop(index)
        _set_branch_cart_custom(custom)
    return redirect(url_for("cart_view"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
@role_required("branch")
def cart_remove(product_id):
    cart = _get_branch_cart()
    key = str(product_id)
    cart.pop(key, None)
    notes = _get_branch_cart_notes()
    notes.pop(key, None)
    _set_branch_cart(cart)
    _set_branch_cart_notes(notes)
    return redirect(url_for("cart_view"))


@app.route("/order/submit", methods=["POST"])
@login_required
@role_required("branch")
def order_submit():
    user = get_current_user()
    bid = get_current_branch_id()
    if not user or not bid:
        flash("Nejprve zvolte pobočku (nebo musíte být přiřazeni k pobočce).", "error")
        return redirect(url_for("cart_view"))
    cart = _get_branch_cart()
    if not cart:
        flash("Košík je prázdný.", "error")
        return redirect(url_for("cart_view"))
    order_type = session.get("order_type", "normal")
    order = Order(branch_id=bid, status="pending", created_by_id=user.id, order_type=order_type)
    db.session.add(order)
    db.session.flush()
    notes = _get_branch_cart_notes()
    placeholder = _get_or_create_custom_placeholder_product()
    if order_type == "internal":
        for pid_str, qty in cart.items():
            if qty <= 0:
                continue
            pid = int(pid_str)
            ip = InternalProduct.query.get(pid)
            if ip:
                branch_note = notes.get(pid_str) if notes else None
                item = OrderItem(
                    order_id=order.id,
                    product_id=placeholder.id,
                    internal_product_id=ip.id,
                    ordered_quantity=qty,
                    branch_note=branch_note,
                )
                db.session.add(item)
    else:
        for pid_str, qty in cart.items():
            if qty <= 0:
                continue
            pid = int(pid_str)
            p = Product.query.get(pid)
            if p:
                branch_note = notes.get(pid_str) if notes else None
                item = OrderItem(
                    order_id=order.id,
                    product_id=p.id,
                    ordered_quantity=qty,
                    branch_note=branch_note,
                )
                db.session.add(item)
        for c in _get_branch_cart_custom():
            if (c.get("quantity") or 0) <= 0:
                continue
            item = OrderItem(
                order_id=order.id,
                product_id=placeholder.id,
                ordered_quantity=c["quantity"],
                custom_product_name=c.get("name", "").strip() or None,
            )
            db.session.add(item)
    db.session.commit()
    audit_log("order_created", "order", order.id, f"Objednávka #{order.id} pro pobočku {bid}")

    # --- SPUŠTĚNÍ NOTIFIKACE NA POZADÍ ---
    branch = Branch.query.get(bid)
    branch_name = branch.name if branch else f"ID {bid}"

    threading.Thread(
        target=notify_worker,
        args=(order.id, branch_name)
    ).start()

    if order_type == "internal":
        _set_branch_cart({})  # vymaže interní košík (session order_type je stále internal)
    else:
        _set_branch_cart({})
        _set_branch_cart_notes({})
        _set_branch_cart_custom([])
    flash("Objednávka odeslána.")
    if order_type == "internal":
        return redirect(url_for("branch_orders", type="internal"))
    return redirect(url_for("branch_orders"))


@app.route("/orders")
@login_required
@role_required("branch")
def branch_orders():
    user = get_current_user()
    bid = get_current_branch_id()
    order_type_filter = request.args.get("type", "normal").strip() or "normal"
    if not bid:
        orders = []
    else:
        orders = Order.query.filter_by(branch_id=bid, order_type=order_type_filter).order_by(Order.created_at.desc()).all()
    return render_template("branch_orders.html", orders=orders, user=user, order_type_filter=order_type_filter)


@app.route("/orders/<int:order_id>")
@login_required
@role_required("branch")
def branch_order_detail(order_id):
    user = get_current_user()
    order = Order.query.get_or_404(order_id)
    if order.branch_id != get_current_branch_id():
        flash("Objednávka nepatří vaší pobočce.", "error")
        return redirect(url_for("branch_orders"))
    total_qty = sum((i.ordered_quantity or 0) for i in order.items)
    shipped_qty = sum((i.shipped_quantity or 0) for i in order.items)
    order_audit_log = (
        AuditLog.query.filter_by(entity_type="order", entity_id=order.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )
    return render_template(
        "branch_order_detail.html",
        order=order,
        user=user,
        status_cz=status_cz,
        total_qty=total_qty,
        shipped_qty=shipped_qty,
        order_audit_log=order_audit_log,
    )


@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    from sqlalchemy import func
    total_orders = Order.query.count()
    by_status = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    status_counts = {s: c for s, c in by_status}
    top_products = (
        db.session.query(Product.id, Product.name, Product.sku, Product.unit, func.sum(OrderItem.ordered_quantity).label("total"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.id, Product.name, Product.sku, Product.unit)
        .order_by(func.sum(OrderItem.ordered_quantity).desc())
        .limit(12)
        .all()
    )
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template(
        "admin_dashboard.html",
        user=get_current_user(),
        total_orders=total_orders,
        status_counts=status_counts,
        top_products=top_products,
        recent_orders=recent_orders,
        status_cz=status_cz,
    )


@app.route("/admin/act-as", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_act_as():
    """Přepnutí admina do režimu pobočky nebo skladu (vše s audit logem)."""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "branch":
            branch_id = request.form.get("branch_id", type=int)
            branch = Branch.query.get(branch_id) if branch_id else None
            if branch:
                session["acting_as_role"] = "branch"
                session["acting_as_branch_id"] = branch.id
                audit_log("admin_act_as", None, None, f"Admin působí jako pobočka: {branch.name} (#{branch.id})")
                flash(f"Režim: působíte jako pobočka {branch.name}. Všechny akce se zapisují do audit logu.")
                return redirect(url_for("branch_dashboard"))
            flash("Zvolte pobočku.", "error")
        elif action == "warehouse":
            session["acting_as_role"] = "warehouse"
            session["acting_as_branch_id"] = None
            audit_log("admin_act_as", None, None, "Admin působí jako sklad")
            flash("Režim: působíte jako sklad. Všechny akce se zapisují do audit logu.")
            return redirect(url_for("warehouse_dashboard"))
        elif action == "end":
            session.pop("acting_as_role", None)
            session.pop("acting_as_branch_id", None)
            audit_log("admin_act_as", None, None, "Admin ukončil režim pobočka/sklad")
            flash("Režim ukončen.")
            return redirect(url_for("admin_dashboard"))
    branches = Branch.query.order_by(Branch.name).all()
    return render_template("admin_act_as.html", branches=branches, user=get_current_user())


@app.route("/admin/orders")
@login_required
@role_required("admin")
def admin_orders():
    status_filter = request.args.get("status", "").strip()
    q = Order.query
    if status_filter:
        q = q.filter(Order.status == status_filter)
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template(
        "admin_orders.html",
        orders=orders,
        user=get_current_user(),
        status_filter=status_filter,
    )


@app.route("/admin/orders/<int:order_id>")
@login_required
@role_required("admin")
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    total_qty = sum((i.ordered_quantity or 0) for i in order.items)
    shipped_qty = sum((i.shipped_quantity or 0) for i in order.items)
    order_audit_log = (
        AuditLog.query.filter_by(entity_type="order", entity_id=order.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )
    return render_template(
        "admin_order_detail.html",
        order=order,
        user=get_current_user(),
        status_cz=status_cz,
        total_qty=total_qty,
        shipped_qty=shipped_qty,
        order_audit_log=order_audit_log,
    )


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_users():
    if request.method == "POST" and request.form.get("action") == "create":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "branch")
        branch_ids = request.form.getlist("branch_ids", type=int) or []
        if not username or not password:
            flash("Uživatelské jméno a heslo jsou povinné.", "error")
            return redirect(url_for("admin_users"))
        if role == "branch" and not branch_ids:
            flash("Uživatel s rolí branch musí být přiřazen k alespoň jedné pobočce.", "error")
            return redirect(url_for("admin_users"))
        if User.query.filter_by(username=username).first():
            flash("Uživatel již existuje.", "error")
            return redirect(url_for("admin_users"))
        u = User(username=username, role=role, branch_id=branch_ids[0] if role == "branch" and branch_ids else None)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
        if role == "branch" and branch_ids:
            for bid in branch_ids:
                b = Branch.query.get(bid)
                if b:
                    u.branches.append(b)
        db.session.commit()
        flash("Účet uživatele vytvořen.")
        return redirect(url_for("admin_users"))
    users = User.query.all()
    branches = Branch.query.order_by(Branch.name).all()
    edit_user_id = request.args.get("edit", type=int)
    return render_template("admin_users.html", users=users, branches=branches, user=get_current_user(), edit_user_id=edit_user_id)


@app.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def admin_user_edit(user_id):
    u = User.query.get_or_404(user_id)
    username = request.form.get("username", "").strip()
    role = request.form.get("role", u.role)
    branch_ids = request.form.getlist("branch_ids", type=int) or []
    new_password = request.form.get("new_password", "")
    if not username:
        flash("Uživatelské jméno je povinné.", "error")
        return redirect(url_for("admin_users"))
    if role == "branch" and not branch_ids:
        flash("Uživatel s rolí branch musí být přiřazen k alespoň jedné pobočce.", "error")
        return redirect(url_for("admin_users"))
    other = User.query.filter(User.username == username, User.id != u.id).first()
    if other:
        flash("Uživatelské jméno již používá jiný účet.", "error")
        return redirect(url_for("admin_users"))
    u.username = username
    u.role = role
    u.branch_id = branch_ids[0] if role == "branch" and branch_ids else None
    if role == "branch":
        u.branches = Branch.query.filter(Branch.id.in_(branch_ids)).all() if branch_ids else []
    else:
        u.branches = []
    if new_password:
        u.set_password(new_password)
    db.session.commit()
    flash("Účet uživatele upraven.")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_user_delete(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == session.get("user_id"):
        flash("Nemůžete smazat vlastní účet.", "error")
        return redirect(url_for("admin_users"))
    if u.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("Nelze smazat posledního administrátora.", "error")
        return redirect(url_for("admin_users"))
    db.session.delete(u)
    db.session.commit()
    flash("Účet uživatele smazán.")
    return redirect(url_for("admin_users"))


@app.route("/admin/branches", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_branches():
    if request.method == "POST" and request.form.get("action") == "create":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip() or None
        if not name:
            flash("Název pobočky je povinný.", "error")
            return redirect(url_for("admin_branches"))
        b = Branch(name=name, code=code)
        db.session.add(b)
        db.session.commit()
        flash("Pobočka přidána.")
        return redirect(url_for("admin_branches"))
    branches = Branch.query.order_by(Branch.name).all()
    edit_branch_id = request.args.get("edit", type=int)
    return render_template("admin_branches.html", branches=branches, user=get_current_user(), edit_branch_id=edit_branch_id)


@app.route("/admin/branches/<int:branch_id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def admin_branch_edit(branch_id):
    b = Branch.query.get_or_404(branch_id)
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip() or None
    if not name:
        flash("Název pobočky je povinný.", "error")
        return redirect(url_for("admin_branches"))
    b.name = name
    b.code = code
    db.session.commit()
    flash("Pobočka upravena.")
    return redirect(url_for("admin_branches"))


@app.route("/admin/branches/<int:branch_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def admin_branch_delete(branch_id):
    b = Branch.query.get_or_404(branch_id)
    if b.orders.count() > 0:
        flash("Pobočku nelze smazat, má objednávky. Nejprve smažte nebo přeřaďte objednávky.", "error")
        return redirect(url_for("admin_branches"))
    for u in b.users:
        u.branch_id = None
    for u in b.branch_users:
        u.branches.remove(b)
    db.session.delete(b)
    db.session.commit()
    flash("Pobočka smazána.")
    return redirect(url_for("admin_branches"))


@app.route("/admin/products")
@login_required
@role_required("admin")
def admin_products():
    """Admin přehled produktů s filtry: skupina, značka, 10mg/20mg, interní."""
    from sqlalchemy import or_
    q = request.args.get("q", "").strip()
    group_filter = request.args.get("group", "").strip() or None
    brand_filter = request.args.get("brand", "").strip() or None
    category_filter = request.args.get("category", "").strip() or None  # 10mg | 20mg
    internal_filter = request.args.get("internal", "").strip() or None  # "0" = běžné, "1" = interní, None = vše
    base = Product.query.filter(Product.name != "[Vlastní – produkt mimo katalog]")
    if internal_filter == "1":
        base = base.filter(Product.is_internal == True)
    elif internal_filter == "0":
        base = base.filter(db.or_(Product.is_internal == False, Product.is_internal.is_(None)))
    if group_filter:
        base = base.filter(Product.group_name == group_filter)
    if q:
        q_like = f"%{q}%"
        products = base.filter(
            or_(Product.name.ilike(q_like), Product.sku.ilike(q_like))
        ).order_by(Product.group_name, Product.name).all()
    else:
        products = base.order_by(Product.group_name, Product.name).all()
    all_for_options = Product.query.filter(Product.name != "[Vlastní – produkt mimo katalog]").all()
    groups = sorted({p.group_name for p in all_for_options if p.group_name})
    brands = sorted({_product_brand(p.name) for p in all_for_options if _product_brand(p.name)})
    if brand_filter:
        products = [p for p in products if _product_brand(p.name) == brand_filter]
    if category_filter and category_filter in PRODUCT_MG_OPTIONS:
        products = [p for p in products if _product_category(p.name) == category_filter]
    categories = PRODUCT_MG_OPTIONS.copy()
    return render_template(
        "admin_products.html",
        products=products,
        user=get_current_user(),
        search_q=q,
        groups=groups,
        group_filter=group_filter,
        brands=brands,
        brand_filter=brand_filter,
        categories=categories,
        category_filter=category_filter,
        internal_filter=internal_filter,
    )


@app.route("/admin/products-internal")
@login_required
@role_required("admin")
def admin_internal_products():
    """Interní produkty (kancelář) – samostatná stránka."""
    products = Product.query.filter(Product.is_internal == True).order_by(Product.group_name, Product.name).all()
    return render_template("admin_internal_products.html", products=products, user=get_current_user())


@app.route("/admin/products/<int:product_id>/set-internal", methods=["POST"])
@login_required
@role_required("admin")
def admin_product_set_internal(product_id):
    product = Product.query.get_or_404(product_id)
    val = request.form.get("internal")
    product.is_internal = str(val).strip().lower() in ("1", "true", "yes", "on")
    db.session.commit()
    audit_log("product_updated", "product", product.id, f"is_internal={product.is_internal}")
    flash("Produkt upraven (interní)." if product.is_internal else "Produkt upraven (běžný).")
    return redirect(request.referrer or url_for("admin_products"))


def _norm(val):
    """Normalizuje hodnotu z buňky na řetězec (Excel může vracet float)."""
    if val is None:
        return None
    if isinstance(val, float):
        if val == int(val):
            val = int(val)
    s = str(val).strip()
    return s if s else None


def _import_csv(path):
    import csv
    added, updated, skipped, errors = 0, 0, 0, 0
    with open(path, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
        f.seek(0)
        # Podpora tabulátoru (TSV): název_skupiny\tnázev\tsku\tpc
        delimiter = "\t" if "\t" in first_line and "název" in first_line.lower() else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            name = (row.get("název") or row.get("nazev") or row.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            try:
                sku = _norm(row.get("sku") or row.get("code") or row.get("kod"))
                unit = _norm(row.get("ks"))  # jednotka: ks, ml, balení
                group_name = _norm(row.get("název_skupiny") or row.get("nazev_skupiny") or row.get("group_name"))
                pc = _norm(row.get("pc"))
                existing = Product.query.filter_by(sku=sku).first() if sku else None
                if not existing:
                    existing = Product.query.filter(Product.name == name).first()
                if existing:
                    existing.name = name
                    existing.sku = sku
                    existing.unit = unit
                    existing.group_name = group_name
                    existing.pc = pc
                    updated += 1
                else:
                    db.session.add(Product(name=name, sku=sku, unit=unit, group_name=group_name, pc=pc))
                    added += 1
                db.session.commit()
            except Exception:
                db.session.rollback()
                errors += 1
    return added, updated, skipped, errors


def _import_internal_csv(path):
    """Import do tabulky internal_products (stejný formát CSV jako běžné produkty)."""
    import csv
    added, updated, skipped, errors = 0, 0, 0, 0
    with open(path, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
        f.seek(0)
        delimiter = "\t" if "\t" in first_line and "název" in first_line.lower() else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            name = (row.get("název") or row.get("nazev") or row.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            try:
                sku = _norm(row.get("sku") or row.get("code") or row.get("kod"))
                unit = _norm(row.get("ks"))
                group_name = _norm(row.get("název_skupiny") or row.get("nazev_skupiny") or row.get("group_name"))
                pc = _norm(row.get("pc"))
                existing = InternalProduct.query.filter_by(sku=sku).first() if sku else None
                if not existing:
                    existing = InternalProduct.query.filter(InternalProduct.name == name).first()
                if existing:
                    existing.name = name
                    existing.sku = sku
                    existing.unit = unit
                    existing.group_name = group_name
                    existing.pc = pc
                    updated += 1
                else:
                    db.session.add(InternalProduct(name=name, sku=sku, unit=unit, group_name=group_name, pc=pc))
                    added += 1
                db.session.commit()
            except Exception:
                db.session.rollback()
                errors += 1
    return added, updated, skipped, errors


def _excel_row_to_product(d):
    """Z řádku Excelu vrátí (name, sku, unit, group_name, pc) nebo None. col2 = ks (jednotka) nebo sku."""
    name = _norm(
        d.get("název") or d.get("nazev") or d.get("name") or d.get("col1")
    )
    if not name:
        return None
    sku = _norm(d.get("sku") or d.get("code") or d.get("kod"))
    unit = _norm(d.get("ks"))  # jednotka: ks, ml, balení (col2 v pořadí skupina,název,ks,pc)
    if not unit and d.get("col2") is not None:
        unit = _norm(d.get("col2"))
    group_name = _norm(
        d.get("název_skupiny") or d.get("nazev_skupiny") or d.get("group_name") or d.get("col0")
    )
    pc = _norm(d.get("pc") or d.get("col3"))
    return (name, sku, unit, group_name, pc)


def _import_excel(path):
    added, updated, skipped, errors = 0, 0, 0, 0

    def process_row(d, row_num):
        nonlocal added, updated, skipped, errors
        t = _excel_row_to_product(d)
        if not t:
            skipped += 1
            return
        name, sku, unit, group_name, pc = t
        try:
            existing = Product.query.filter_by(sku=sku).first() if sku else None
            if not existing:
                existing = Product.query.filter(Product.name == name).first()
            if existing:
                existing.name = name
                existing.sku = sku
                existing.unit = unit
                existing.group_name = group_name
                existing.pc = pc
                updated += 1
            else:
                db.session.add(Product(name=name, sku=sku, unit=unit, group_name=group_name, pc=pc))
                added += 1
            db.session.commit()
        except Exception:
            db.session.rollback()
            errors += 1

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        headers_raw = [c.value for c in ws[1]]
        headers = [str(h or "").strip().lower().replace(" ", "_").replace("-", "_") for h in headers_raw]
        ncols = len(headers)
        for row_num, row in enumerate(ws.iter_rows(min_row=2), start=2):
            vals = [c.value for c in row]
            d = dict(zip(headers, vals))
            for i in range(4):
                d["col%d" % i] = vals[i] if i < len(vals) else None
            process_row(d, row_num)
        wb.close()
    except Exception:
        import xlrd
        wb = xlrd.open_workbook(path)
        sheet = wb.sheet_by_index(0)
        ncols = sheet.ncols
        headers = []
        for c in range(ncols):
            v = sheet.cell_value(0, c)
            headers.append(str(v or "").strip().lower().replace(" ", "_").replace("-", "_"))
        for r in range(1, sheet.nrows):
            d = {}
            for c in range(ncols):
                val = sheet.cell_value(r, c)
                if headers[c]:
                    d[headers[c]] = val
                if c < 4:
                    d["col%d" % c] = val
            process_row(d, r + 1)
    return added, updated, skipped, errors


@app.route("/admin/import", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_import():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Vyberte soubor.", "error")
            return redirect(url_for("admin_import"))
        ext = os.path.splitext(f.filename)[1].lower()
        path = os.path.join(app.config["UPLOAD_FOLDER"], f.filename)
        f.save(path)
        try:
            if ext == ".csv":
                added, updated, skipped, errors = _import_csv(path)
            elif ext in (".xls", ".xlsx"):
                added, updated, skipped, errors = _import_excel(path)
            else:
                flash("Podporované formáty: CSV, XLS, XLSX.", "error")
                return redirect(url_for("admin_import"))
            msg = f"Import dokončen. Přidáno: {added}, aktualizováno: {updated}"
            if skipped:
                msg += f", přeskočeno (prázdný název): {skipped}"
            if errors:
                msg += f", chyba při zpracování: {errors} řádků"
            msg += "."
            flash(msg)
        except Exception as e:
            flash(f"Chyba importu: {e}", "error")
        finally:
            if os.path.exists(path):
                os.remove(path)
        return redirect(url_for("admin_import"))
    return render_template("admin_import.html", user=get_current_user())


def _import_orders_csv(path):
    """Import objednávek z CSV: branch_code, product_id, quantity. Řádky se stejným branch_code = jedna objednávka."""
    import csv
    from collections import defaultdict
    created = 0
    errors = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Prázdný soubor nebo chybějící hlavička")
        cols = [c.strip().lower().replace(" ", "_") for c in reader.fieldnames]
        rows_by_branch = defaultdict(list)
        for row in reader:
            row = {cols[i]: (v.strip() if isinstance(v, str) else v) for i, v in enumerate(row.values()) if i < len(cols)}
            branch_code = (row.get("branch_code") or row.get("pobocka") or "").strip()
            pid_raw = row.get("product_id") or row.get("product_id") or ""
            qty = row.get("quantity")
            if not branch_code:
                errors.append("Chybějící branch_code")
                continue
            try:
                qty = float(qty) if qty not in (None, "") else 0
            except (TypeError, ValueError):
                errors.append(f"Neplatné množství: {qty}")
                continue
            if qty <= 0:
                continue
            rows_by_branch[branch_code].append({"product_id": pid_raw, "quantity": qty})
    branch_by_code = {b.code: b for b in Branch.query.all() if b.code}
    placeholder = _get_or_create_custom_placeholder_product()
    user = get_current_user()
    for branch_code, rows in rows_by_branch.items():
        branch = branch_by_code.get(branch_code)
        if not branch:
            errors.append(f"Pobočka s kódem '{branch_code}' neexistuje")
            continue
        order = Order(branch_id=branch.id, status="pending", created_by_id=user.id if user else None, order_type="normal")
        db.session.add(order)
        db.session.flush()
        for r in rows:
            pid_raw = (r["product_id"] or "").strip()
            if pid_raw.isdigit():
                product = Product.query.get(int(pid_raw))
                if not product:
                    errors.append(f"Produkt id {pid_raw} neexistuje")
                    continue
                item = OrderItem(order_id=order.id, product_id=product.id, ordered_quantity=r["quantity"])
            else:
                item = OrderItem(order_id=order.id, product_id=placeholder.id, ordered_quantity=r["quantity"], custom_product_name=pid_raw or None)
            db.session.add(item)
        db.session.commit()
        audit_log("order_created", "order", order.id, f"Import objednávky pro pobočku {branch_code}")
        created += 1
    return created, errors


def _import_vydejky_csv(path):
    """Import výdejek z CSV: order_id, order_item_id, shipped_quantity. Aktualizuje odeslané množství."""
    import csv
    updated = 0
    errors = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Prázdný soubor nebo chybějící hlavička")
        cols = [c.strip().lower().replace(" ", "_") for c in reader.fieldnames]
        for row in reader:
            row = {cols[i]: (v.strip() if isinstance(v, str) else v) for i, v in enumerate(row.values()) if i < len(cols)}
            oid = row.get("order_id")
            iid = row.get("order_item_id") or row.get("item_id")
            shipped = row.get("shipped_quantity")
            if not oid or not iid:
                errors.append("Chybějící order_id nebo order_item_id")
                continue
            try:
                oid, iid = int(oid), int(iid)
                shipped = float(shipped) if shipped not in (None, "") else 0
            except (TypeError, ValueError):
                errors.append(f"Neplatné číslo: order_id={oid}, item_id={iid}, shipped={shipped}")
                continue
            if shipped < 0:
                continue
            item = OrderItem.query.filter_by(id=iid, order_id=oid).first()
            if not item:
                errors.append(f"Položka order_item_id={iid} v objednávce {oid} neexistuje")
                continue
            item.shipped_quantity = shipped
            order = Order.query.get(oid)
            if order:
                _update_order_status_from_items(order)
            updated += 1
    db.session.commit()
    return updated, errors


@app.route("/admin/import-orders", methods=["POST"])
@login_required
@role_required("admin")
def admin_import_orders():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Vyberte soubor.", "error")
        return redirect(url_for("admin_import"))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext != ".csv":
        flash("Import objednávek podporuje pouze CSV.", "error")
        return redirect(url_for("admin_import"))
    path = os.path.join(app.config["UPLOAD_FOLDER"], f.filename)
    f.save(path)
    try:
        created, errors = _import_orders_csv(path)
        msg = f"Import objednávek: vytvořeno {created} objednávek."
        if errors:
            msg += " Chyby: " + "; ".join(errors[:10])
            if len(errors) > 10:
                msg += f" (+{len(errors) - 10} dalších)"
        flash(msg)
    except Exception as e:
        flash(f"Chyba importu objednávek: {e}", "error")
    finally:
        if os.path.exists(path):
            os.remove(path)
    return redirect(url_for("admin_import"))


@app.route("/admin/import-vydejky", methods=["POST"])
@login_required
@role_required("admin")
def admin_import_vydejky():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Vyberte soubor.", "error")
        return redirect(url_for("admin_import"))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext != ".csv":
        flash("Import výdejek podporuje pouze CSV.", "error")
        return redirect(url_for("admin_import"))
    path = os.path.join(app.config["UPLOAD_FOLDER"], f.filename)
    f.save(path)
    try:
        updated, errors = _import_vydejky_csv(path)
        msg = f"Import výdejek: aktualizováno {updated} položek."
        if errors:
            msg += " Chyby: " + "; ".join(errors[:10])
            if len(errors) > 10:
                msg += f" (+{len(errors) - 10} dalších)"
        flash(msg)
    except Exception as e:
        flash(f"Chyba importu výdejek: {e}", "error")
    finally:
        if os.path.exists(path):
            os.remove(path)
    return redirect(url_for("admin_import"))


@app.route("/admin/import-internal", methods=["POST"])
@login_required
@role_required("admin")
def admin_import_internal():
    """Import interních produktů do tabulky internal_products (CSV, stejný formát jako běžné produkty)."""
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Vyberte soubor.", "error")
        return redirect(url_for("admin_import"))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext != ".csv":
        flash("Import interních produktů podporuje pouze CSV.", "error")
        return redirect(url_for("admin_import"))
    path = os.path.join(app.config["UPLOAD_FOLDER"], f.filename)
    f.save(path)
    try:
        added, updated, skipped, errors = _import_internal_csv(path)
        msg = f"Import interních produktů: přidáno {added}, aktualizováno {updated}"
        if skipped:
            msg += f", přeskočeno: {skipped}"
        if errors:
            msg += f", chyba: {errors} řádků"
        msg += "."
        flash(msg)
    except Exception as e:
        flash(f"Chyba importu interních produktů: {e}", "error")
    finally:
        if os.path.exists(path):
            os.remove(path)
    return redirect(url_for("admin_import"))


@app.route("/warehouse")
@login_required
@role_required("warehouse")
def warehouse_dashboard():
    from sqlalchemy import func
    total_orders = Order.query.count()
    by_status = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    status_counts = {s: c for s, c in by_status}
    top_products = (
        db.session.query(Product.id, Product.name, Product.sku, Product.unit, func.sum(OrderItem.ordered_quantity).label("total"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.id, Product.name, Product.sku, Product.unit)
        .order_by(func.sum(OrderItem.ordered_quantity).desc())
        .limit(12)
        .all()
    )
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template(
        "warehouse_dashboard.html",
        user=get_current_user(),
        total_orders=total_orders,
        status_counts=status_counts,
        top_products=top_products,
        recent_orders=recent_orders,
        status_cz=status_cz,
    )


@app.route("/warehouse/orders")
@login_required
@role_required("warehouse")
def warehouse_orders():
    status_filter = request.args.get("status", "").strip()
    q = Order.query
    if status_filter:
        q = q.filter(Order.status == status_filter)
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template(
        "warehouse_orders.html",
        orders=orders,
        user=get_current_user(),
        status_filter=status_filter,
    )


@app.route("/warehouse/orders/new", methods=["GET", "POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_order_new():
    """Sklad vytvoří objednávku a přiřadí ji pobočce (created_by_warehouse_id)."""
    branches = Branch.query.order_by(Branch.name).all()
    base_products = Product.query.filter(
        Product.name != "[Vlastní – produkt mimo katalog]",
        db.or_(Product.is_internal == False, Product.is_internal.is_(None)),
    ).order_by(Product.group_name, Product.name).all()
    if request.method == "POST":
        branch_id = request.form.get("branch_id", type=int)
        branch = Branch.query.get(branch_id) if branch_id else None
        if not branch:
            flash("Zvolte pobočku.", "error")
            return render_template("warehouse_order_new.html", branches=branches, products=base_products, user=get_current_user())
        user = get_current_user()
        order = Order(
            branch_id=branch.id,
            status="pending",
            created_by_id=None,
            order_type="normal",
            created_by_warehouse_id=user.id if user else None,
        )
        db.session.add(order)
        db.session.flush()
        added = 0
        for p in base_products:
            key = f"qty_{p.id}"
            try:
                qty = request.form.get(key, type=float)
            except (TypeError, ValueError):
                qty = None
            if qty is not None and qty > 0:
                db.session.add(OrderItem(order_id=order.id, product_id=p.id, ordered_quantity=qty))
                added += 1
        if added == 0:
            db.session.rollback()
            flash("Přidejte alespoň jednu položku s množstvím.", "error")
            return render_template("warehouse_order_new.html", branches=branches, products=base_products, user=get_current_user())
        db.session.commit()
        audit_log("order_created", "order", order.id, f"Sklad vytvořil objednávku pro pobočku {branch.name} (#{branch.id})")
        flash(f"Objednávka #{order.id} pro pobočku {branch.name} vytvořena.")
        return redirect(url_for("warehouse_order_detail", order_id=order.id))
    return render_template("warehouse_order_new.html", branches=branches, products=base_products, user=get_current_user())


@app.route("/warehouse/order/<int:order_id>")
@login_required
@role_required("warehouse", "admin")
def warehouse_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    total_qty = sum((i.ordered_quantity or 0) for i in order.items)
    shipped_qty = sum((i.shipped_quantity or 0) for i in order.items)
    order_audit_log = (
        AuditLog.query.filter_by(entity_type="order", entity_id=order.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )
    return render_template(
        "warehouse_order_detail.html",
        order=order,
        user=get_current_user(),
        status_cz=status_cz,
        total_qty=total_qty,
        shipped_qty=shipped_qty,
        order_audit_log=order_audit_log,
    )


@app.route("/warehouse/order/<int:order_id>/status", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")
    if status in ORDER_STATUSES:
        order.status = status
        db.session.commit()
        audit_log("order_status", "order", order.id, f"Objednávka #{order_id} → {status}")
        flash("Stav objednávky změněn.")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


def _update_order_status_from_items(order):
    """Nastaví stav objednávky podle odeslaných množství: všechny položky odeslány -> shipped, jinak částečně -> partially_shipped."""
    if not order.items:
        return
    all_shipped = all(
        (it.shipped_quantity or 0) >= (it.ordered_quantity or 0)
        for it in order.items
    )
    any_shipped = any((it.shipped_quantity or 0) > 0 for it in order.items)
    if all_shipped:
        order.status = "shipped"
    elif any_shipped:
        order.status = "partially_shipped"


@app.route("/warehouse/order/<int:order_id>/item/<int:item_id>/shipped", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_item_shipped(order_id, item_id):
    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first_or_404()
    shipped = request.form.get("shipped_quantity", type=float)
    if shipped is not None and shipped >= 0:
        item.shipped_quantity = shipped
        order = Order.query.get(order_id)
        _update_order_status_from_items(order)
        db.session.commit()
        audit_log("order_item_shipped", "order_item", item.id, f"Objednávka #{order_id}, odesláno {shipped}")
        audit_log("order_item_shipped", "order", order_id, f"Položka {item.display_name()}: odesláno {shipped}")
        flash("Dodané množství upraveno.")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


@app.route("/warehouse/order/<int:order_id>/item/<int:item_id>/unavailable", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_item_unavailable(order_id, item_id):
    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first_or_404()
    item.unavailable = True
    item.shipped_quantity = 0
    db.session.commit()
    audit_log("order_item_unavailable", "order_item", item.id, f"Objednávka #{order_id}, položka {item.display_name()}")
    audit_log("order_item_unavailable", "order", order_id, f"Položka {item.display_name()} – Nemám skladem")
    flash("Položka označena jako „Nemám na skladě“.")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


@app.route("/warehouse/order/<int:order_id>/item/<int:item_id>/available", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_item_available(order_id, item_id):
    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first_or_404()
    item.unavailable = False
    db.session.commit()
    audit_log("order_item_available", "order_item", item.id, f"Objednávka #{order_id}, položka {item.display_name()}")
    audit_log("order_item_available", "order", order_id, f"Položka {item.display_name()} – Má skladem")
    flash("Položka znovu označena jako „Má skladem“.")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


@app.route("/warehouse/order/<int:order_id>/item/<int:item_id>/note", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_item_note(order_id, item_id):
    item = OrderItem.query.filter_by(id=item_id, order_id=order_id).first_or_404()
    note = request.form.get("warehouse_note", "").strip() or None
    item.warehouse_note = note
    db.session.commit()
    if note:
        audit_log("order_item_note", "order_item", item.id, f"Poznámka skladu k položce (objednávka #{order_id})")
    flash("Poznámka skladu uložena." if note else "Poznámka skladu odebrána.")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


def _order_invoice_update(order_id):
    """Společná logika nastavení faktury (volá sklad i pobočka). Vrací True pokud byla změna."""
    order = Order.query.get_or_404(order_id)
    ok_val = request.form.get("invoice_ok")
    note = request.form.get("invoice_note", "").strip() or None
    if ok_val == "1":
        order.invoice_ok = True
        order.invoice_note = None
        db.session.commit()
        audit_log("invoice_ok", "order", order.id, f"Objednávka #{order_id} – Vše cajk")
        return True
    if ok_val == "0":
        if not note:
            return False
        order.invoice_ok = False
        order.invoice_note = note
        db.session.commit()
        audit_log("invoice_error", "order", order.id, f"Objednávka #{order_id}: {note[:200]}")
        return True
    return False


@app.route("/warehouse/order/<int:order_id>/invoice", methods=["POST"])
@login_required
@role_required("warehouse", "admin")
def warehouse_order_invoice(order_id):
    if not _order_invoice_update(order_id):
        flash("U stavu „Chyba“ je poznámka povinná.", "error")
    return redirect(url_for("warehouse_order_detail", order_id=order_id))


@app.route("/branch/order/<int:order_id>/invoice", methods=["POST"])
@login_required
@role_required("branch")
def branch_order_invoice(order_id):
    order = Order.query.get_or_404(order_id)
    if order.branch_id != get_current_branch_id():
        flash("Objednávka nepatří vaší pobočce.", "error")
        return redirect(url_for("branch_orders"))
    if not _order_invoice_update(order_id):
        flash("U stavu „Chyba“ je poznámka povinná.", "error")
    return redirect(url_for("branch_order_detail", order_id=order_id))


with app.app_context():
    from sqlalchemy import text
    db.create_all()
    # Migrace: vytvořit user_branches, pokud chybí (staré DB nebo create_all ji neudělal)
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_branches (
                user_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, branch_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (branch_id) REFERENCES branches (id)
            )
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id),
                username VARCHAR(80) NOT NULL,
                action VARCHAR(80) NOT NULL,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                details TEXT
            )
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Doplnit nové sloupce v order_items / products, pokud ještě neexistují (pro existující DB)
    for sql in (
        "ALTER TABLE order_items ADD COLUMN branch_note VARCHAR(255)",
        "ALTER TABLE order_items ADD COLUMN unavailable INTEGER DEFAULT 0",
        "ALTER TABLE order_items ADD COLUMN custom_product_name VARCHAR(255)",
        "ALTER TABLE products ADD COLUMN group_name VARCHAR(255)",
        "ALTER TABLE products ADD COLUMN pc VARCHAR(100)",
        "ALTER TABLE products ADD COLUMN unit VARCHAR(50)",
        "ALTER TABLE products ADD COLUMN is_internal INTEGER DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN created_by_id INTEGER REFERENCES users(id)",
        "ALTER TABLE orders ADD COLUMN invoice_ok INTEGER",
        "ALTER TABLE orders ADD COLUMN invoice_note TEXT",
        "ALTER TABLE orders ADD COLUMN order_type VARCHAR(30) DEFAULT 'normal'",
        "ALTER TABLE orders ADD COLUMN created_by_warehouse_id INTEGER REFERENCES users(id)",
    ):
        try:
            db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()
    # Tabulka internal_products (samostatná od products) – před přidáním FK z order_items
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS internal_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                sku VARCHAR(100),
                unit VARCHAR(50),
                group_name VARCHAR(255),
                pc VARCHAR(100)
            )
        """))
        db.session.commit()
    except Exception:
        db.session.rollback()
    for sql in (
        "ALTER TABLE order_items ADD COLUMN internal_product_id INTEGER REFERENCES internal_products(id)",
        "ALTER TABLE branch_carts ADD COLUMN cart_internal_json TEXT DEFAULT '{}'",
    ):
        try:
            db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()
    # Migrace: naplnit user_branches z existujícího branch_id
    try:
        for u in User.query.filter(User.branch_id.isnot(None)):
            b = Branch.query.get(u.branch_id)
            if b and b not in list(u.branches):
                u.branches.append(b)
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Seed admin jen když neexistuje; při Gunicornu (více workery) může běžet
    # souběžně – ošetříme race condition pomocí try/except.
    if not User.query.filter_by(username="admin").first():
        try:
            u = User(username="admin", role="admin")
            u.set_password("admin")
            db.session.add(u)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # Jiný worker už admina vložil – OK
            pass


def _seed_admin():
    """Jednorázově vytvoří admina (pro flask seed-admin nebo ruční volání)."""
    if User.query.filter_by(username="admin").first():
        return False
    u = User(username="admin", role="admin")
    u.set_password("admin")
    db.session.add(u)
    db.session.commit()
    return True


@app.cli.command("seed-admin")
def seed_admin_cmd():
    """Vytvoří výchozího admina (username: admin, heslo: admin). Spusť jednou: flask seed-admin"""
    if _seed_admin():
        print("Admin uživatel vytvořen (admin / admin).")
    else:
        print("Admin uživatel již existuje.")


def _reset_db(seed_admin=True):
    """Smaže všechny tabulky, znovu je vytvoří. Po resetu vždy vytvoří výchozího admina (admin/admin)."""
    db.drop_all()
    db.create_all()
    if seed_admin:
        _seed_admin()
    return True


@app.cli.command("reset-db")
@click.option("--no-seed", is_flag=True, help="Po resetu nevytvářet výchozího admina")
def reset_db_cmd(no_seed):
    """Smaže a znovu vytvoří celou databázi. POZOR: smaže všechna data! Vytvoří admin/admin."""
    with app.app_context():
        _reset_db(seed_admin=not no_seed)
    click.echo("Databáze byla resetována." + ("" if no_seed else " Admin vytvořen (admin/admin)."))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
