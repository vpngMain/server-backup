"""Vaping směnovač – plánování směn."""
import os

try:
    from dotenv import load_dotenv, find_dotenv
    from pathlib import Path
    # Načíst .env – ze složky app nebo vyhledat od CWD
    p = Path(__file__).resolve().parent / ".env"
    if not load_dotenv(p) and find_dotenv():
        load_dotenv(find_dotenv())
except ImportError:
    pass
import io
import csv
from flask import Flask, render_template, redirect, url_for, request, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_, text
from database import db, User, Branch, Employee, ShiftPreset, Shift, EmployeeRequest, RegistrationRequest, PasswordResetToken, PasswordResetRequest, init_db
from coverage import compute_coverage_month, coverage_month_to_grid_response

# Cache pro kontrolu pokrytí – invaliduje se při změně směn
_coverage_cache = {}


def _invalidate_coverage_cache():
    """Invalidace cache při create/update/delete směny."""
    _coverage_cache.clear()


def _parse_branch_id(value, allow_none=False):
    """Vrátí (int_id, None) nebo (None, chybová_hláška)."""
    if value is None or value == "":
        return (None, "Chybí ID pobočky") if not allow_none else (None, None)
    try:
        return (int(value), None)
    except (TypeError, ValueError):
        return (None, "Neplatné ID pobočky")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
# Diagnostika SMTP při startu (MAIL_DEBUG=1)
if os.environ.get("MAIL_DEBUG") == "1":
    h, f = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_FROM")
    import sys
    print(f"[mailer] SMTP_HOST={h or '(chybí)'} MAIL_FROM={f or '(chybí)'}", file=sys.stderr)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///smeny.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Přihlaste se."


@login_manager.user_loader
def load_user(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


@app.context_processor
def inject_config():
    return {"allow_registration": os.environ.get("ALLOW_REGISTRATION", "1") == "1"}


# ============ Health (monitoring) ============
@app.route("/health")
def health():
    """Endpoint pro monitoring – ověření, že aplikace běží a DB reaguje."""
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return jsonify({"status": "ok" if db_status == "ok" else "degraded", "database": db_status}), 200 if db_status == "ok" else 503


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Přihlaste se"}), 401
        if not current_user.is_admin():
            return jsonify({"error": "Přístup jen pro administrátory"}), 403
        return f(*args, **kwargs)
    return decorated


def shift_manager_required(f):
    """Admin nebo účetní – může spravovat směny."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Přihlaste se"}), 401
        if not current_user.can_manage_shifts():
            return jsonify({"error": "Přístup jen pro administrátory a účetní"}), 403
        return f(*args, **kwargs)
    return decorated


# ============ PWA ============
def _load_icon_png(size):
    """Načte ikonu: pokud existuje static/icon.png, použije ji (změněnou na size); jinak vygeneruje modrý čtverec."""
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    icon_path = os.path.join(static_dir, "icon.png")
    try:
        from PIL import Image
        if os.path.isfile(icon_path):
            img = Image.open(icon_path).convert("RGBA")
            resample = getattr(Image, "LANCZOS", getattr(Image, "Resampling", None) and Image.Resampling.LANCZOS or None)
            img = img.resize((size, size), resample if resample is not None else Image.NEAREST)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
        img = Image.new("RGB", (size, size), "#2563eb")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return None


@app.route("/sw.js")
def serve_sw():
    """Service worker na kořeni – nutné pro scope="/"."""
    return app.send_static_file("sw.js"), 200, {"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}


@app.route("/api/icon/<int:size>")
def api_icon(size):
    if size not in (180, 192, 512):
        size = 192
    data = _load_icon_png(size)
    if data:
        return Response(data, mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})
    return "", 404


# ============ Auth ============
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Stránka pro žádost o reset hesla. Vytvoří pouze žádost – admin ji schválí a teprve pak přijde e-mail."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return render_template("forgot_password.html")
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        email = (data.get("email") or "").strip().lower()
        if not email:
            err = "E-mail je povinný."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("forgot_password.html", error=err)
        user = User.query.filter_by(email=email).first()
        msg = "Žádost byla odeslána. Administrátor vás bude kontaktovat e-mailem s odkazem na nastavení hesla."
        if user:
            existing = PasswordResetRequest.query.filter_by(email=email, status="pending").first()
            if not existing:
                from datetime import datetime
                req = PasswordResetRequest(email=email, user_id=user.id, status="pending", created_at=datetime.utcnow().isoformat()[:19])
                db.session.add(req)
                db.session.commit()
        if request.is_json:
            return jsonify({"ok": True, "message": msg})
        return render_template("forgot_password.html", success=msg)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        user = User.query.filter_by(email=data.get("email")).first()
        if user and check_password_hash(user.password_hash, data.get("password", "")):
            login_user(user)
            if request.is_json:
                return jsonify({"ok": True, "redirect": url_for("dashboard")})
            return redirect(url_for("dashboard"))
        err = "Neplatný e-mail nebo heslo."
        if request.is_json:
            return jsonify({"ok": False, "error": err}), 400
        return render_template("login.html", error=err)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    allow_reg = os.environ.get("ALLOW_REGISTRATION", "1") == "1"
    if not allow_reg:
        return render_template("register.html", error="Registrace je uzavřena. Kontaktujte administrátora.")
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        email = (data.get("email") or "").strip().lower()
        name = (data.get("name") or "").strip()
        if not email:
            err = "E-mail je povinný."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("register.html", error=err)
        if User.query.filter_by(email=email).first():
            err = "Tento e-mail je už registrovaný."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("register.html", error=err)
        pending = RegistrationRequest.query.filter_by(email=email, status="pending").first()
        if pending:
            err = "Žádost s tímto e-mailem již čeká na schválení."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("register.html", error=err)
        from datetime import datetime
        req = RegistrationRequest(
            email=email,
            name=name or email.split("@")[0],
            status="pending",
            created_at=datetime.utcnow().isoformat()[:19],
        )
        db.session.add(req)
        db.session.commit()
        if request.is_json:
            return jsonify({"ok": True, "message": "Žádost odeslána. Po schválení přijde e-mail s odkazem na vytvoření hesla."})
        return render_template("register.html", success="Žádost odeslána. Po schválení administrátorem vám přijde e-mail s odkazem na vytvoření hesla.")
    return render_template("register.html")


def _send_reset_password_email(user):
    """Vytvoří token a odešle e-mail s odkazem na reset hesla."""
    import secrets
    from datetime import datetime, timedelta
    PasswordResetToken.query.filter_by(user_id=user.id).delete()
    token = secrets.token_urlsafe(32)
    exp = datetime.utcnow() + timedelta(hours=1)
    prt = PasswordResetToken(user_id=user.id, token=token, expires_at=exp.isoformat()[:19])
    db.session.add(prt)
    db.session.commit()
    try:
        from mailer import notify_reset_password_link
        base_url = (os.environ.get("APP_URL") or "").strip().rstrip("/") or request.host_url.rstrip("/")
        reset_url = f"{base_url}{url_for('reset_password', token=token)}"
        notify_reset_password_link(user.email, reset_url)
    except Exception as ex:
        import sys
        db.session.delete(prt)
        db.session.commit()
        print(f"[mailer] Chyba odeslání reset linku: {ex}", file=sys.stderr)
        raise ex


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """Stránka pro reset hesla (odkaz z e-mailu)."""
    token = request.args.get("token") or (request.get_json(silent=True) or {}).get("token")
    if not token:
        return render_template("reset_password.html", error="Chybí platný odkaz.")
    prt = PasswordResetToken.query.filter_by(token=token).first()
    if not prt:
        return render_template("reset_password.html", error="Odkaz vypršel nebo není platný.")
    from datetime import datetime
    try:
        exp = datetime.fromisoformat(prt.expires_at.replace("Z", "+00:00"))
        if exp.timestamp() < datetime.utcnow().timestamp():
            PasswordResetToken.query.filter_by(id=prt.id).delete()
            db.session.commit()
            return render_template("reset_password.html", error="Odkaz vypršel.")
    except Exception:
        pass
    user = prt.user
    if not user:
        return render_template("reset_password.html", error="Uživatel nenalezen.")
    if request.method == "GET":
        return render_template("reset_password.html", token=token, email=user.email)
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        password = (data.get("password") or "").strip()
        password2 = (data.get("password2") or data.get("password")) or ""
        if password != password2:
            err = "Hesla se neshodují."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("reset_password.html", token=token, email=user.email, error=err)
        if not password or len(password) < 6:
            err = "Heslo musí mít min. 6 znaků."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("reset_password.html", token=token, email=user.email, error=err)
        user.password_hash = generate_password_hash(password)
        db.session.delete(prt)
        db.session.commit()
        login_user(user)
        if request.is_json:
            return jsonify({"ok": True, "redirect": url_for("dashboard")})
        return redirect(url_for("dashboard"))


@app.route("/set-password", methods=["GET", "POST"])
def set_password():
    """Stránka pro vytvoření hesla po schválení registrace (odkaz z e-mailu)."""
    token = request.args.get("token") or (request.get_json(silent=True) or {}).get("token")
    if not token:
        return render_template("set_password.html", error="Chybí platný odkaz.")
    req = RegistrationRequest.query.filter_by(token=token, status="approved").first()
    if not req or not req.approved_user_id:
        return render_template("set_password.html", error="Odkaz vypršel nebo není platný.")
    from datetime import datetime
    if req.token_expires:
        try:
            exp = datetime.fromisoformat(req.token_expires.replace("Z", "+00:00"))
            if exp.timestamp() < datetime.utcnow().timestamp():
                return render_template("set_password.html", error="Odkaz vypršel.")
        except Exception:
            pass
    user = db.session.get(User, req.approved_user_id)
    if not user:
        return render_template("set_password.html", error="Uživatel nenalezen.")
    if request.method == "GET":
        return render_template("set_password.html", token=token, email=user.email)
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        password = (data.get("password") or "").strip()
        password2 = (data.get("password2") or data.get("password")) or ""
        if password != password2:
            err = "Hesla se neshodují."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("set_password.html", token=token, email=user.email, error=err)
        if not password or len(password) < 6:
            err = "Heslo musí mít min. 6 znaků."
            if request.is_json:
                return jsonify({"ok": False, "error": err}), 400
            return render_template("set_password.html", token=token, email=user.email, error=err)
        user.password_hash = generate_password_hash(password)
        req.token = None
        req.token_expires = None
        db.session.commit()
        login_user(user)
        if request.is_json:
            return jsonify({"ok": True, "redirect": url_for("dashboard")})
        return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ============ Dashboard ============
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/me")
@login_required
def api_me():
    data = {
        "id": str(current_user.id),
        "role": current_user.role or "admin",
        "isAdmin": current_user.can_manage_shifts(),
        "isFullAdmin": current_user.is_full_admin(),
    }
    if current_user.is_employee() and current_user.employee:
        data["employee"] = current_user.employee.to_dict()
    if current_user.ical_token:
        base = (os.environ.get("APP_URL") or "").strip().rstrip("/") or request.host_url.rstrip("/")
        data["icalSubscribeUrl"] = f"{base}/api/export/ical?token={current_user.ical_token}"
    return jsonify(data)


@app.route("/api/users/me/generate-ical-token", methods=["POST"])
@login_required
def generate_ical_token():
    """Vygeneruje token pro odběr kalendáře (Apple/iOS)."""
    import secrets
    token = secrets.token_urlsafe(32)
    current_user.ical_token = token
    db.session.commit()
    base = (os.environ.get("APP_URL") or "").strip().rstrip("/") or request.host_url.rstrip("/")
    return jsonify({"icalSubscribeUrl": f"{base}/api/export/ical?token={token}"})


# ============ Branches ============
@app.route("/api/branches", methods=["GET"])
@login_required
@shift_manager_required
def list_branches():
    branches = Branch.query.filter_by(user_id=current_user.owner_id()).all()
    return jsonify([b.to_dict() for b in branches])


@app.route("/api/branches", methods=["POST"])
@login_required
@admin_required
def create_branch():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON (Content-Type: application/json)"}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Název pobočky je povinný"}), 400
    rate = data.get("defaultHourlyRate")
    open_t = (data.get("openTime") or "08:00")[:5]
    close_t = (data.get("closeTime") or "20:00")[:5]
    open_w = (data.get("openTimeWeekend") or "")[:5] or None
    close_w = (data.get("closeTimeWeekend") or "")[:5] or None
    b = Branch(user_id=current_user.id, name=name, address=data.get("address"), default_hourly_rate=float(rate) if rate not in (None, "") else None, open_time=open_t, close_time=close_t, open_time_weekend=open_w, close_time_weekend=close_w)
    db.session.add(b)
    db.session.commit()
    _invalidate_coverage_cache()
    return jsonify(b.to_dict()), 201


@app.route("/api/branches/<int:bid>", methods=["PATCH", "DELETE"])
@login_required
@admin_required
def branch(bid):
    b = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    if request.method == "DELETE":
        db.session.delete(b)
        db.session.commit()
        _invalidate_coverage_cache()
        return "", 204
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    if "name" in data:
        b.name = data["name"]
    if "address" in data:
        b.address = data["address"]
    if "defaultHourlyRate" in data:
        r = data["defaultHourlyRate"]
        b.default_hourly_rate = float(r) if r is not None and r != "" else None
    if "openTime" in data:
        b.open_time = (data.get("openTime") or "08:00")[:5]
    if "closeTime" in data:
        b.close_time = (data.get("closeTime") or "20:00")[:5]
    if "openTimeWeekend" in data:
        v = (data.get("openTimeWeekend") or "").strip()[:5]
        b.open_time_weekend = v if v else None
    if "closeTimeWeekend" in data:
        v = (data.get("closeTimeWeekend") or "").strip()[:5]
        b.close_time_weekend = v if v else None
    db.session.commit()
    _invalidate_coverage_cache()
    return jsonify(b.to_dict())


# ============ Employees ============
@app.route("/api/employees", methods=["GET"])
@login_required
@shift_manager_required
def list_employees():
    branch_id = request.args.get("branchId")
    q = Employee.query.filter(Employee.branch.has(user_id=current_user.owner_id()))
    if branch_id:
        bid, bid_err = _parse_branch_id(branch_id, allow_none=True)
        if bid_err:
            return jsonify({"error": bid_err}), 400
        if bid is not None:
            q = q.filter(Employee.branch_id == bid)
    employees = q.all()
    out = []
    for e in employees:
        d = e.to_dict()
        d["hasAccess"] = User.query.filter_by(employee_id=e.id).first() is not None
        out.append(d)
    return jsonify(out)


@app.route("/api/employees", methods=["POST"])
@login_required
@admin_required
def create_employee():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    branch_id = data.get("branchId")
    bid, bid_err = _parse_branch_id(branch_id)
    if bid_err:
        return jsonify({"error": bid_err or "Pobočka je povinná"}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Jméno zaměstnance je povinné"}), 400
    branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    rate = data.get("hourlyRate")
    color = (data.get("color") or "").strip() or None
    if color and not color.startswith("#"):
        color = "#" + color
    e = Employee(branch_id=branch.id, name=name, email=data.get("email"), hourly_rate=float(rate) if rate is not None and rate != "" else None, color=color[:8] if color else None)
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@app.route("/api/accountants", methods=["GET"])
@login_required
@admin_required
def list_accountants():
    """Seznam účetních spravovaných tímto adminem."""
    users = User.query.filter_by(role="ucetni", manages_user_id=current_user.id).order_by(User.email).all()
    return jsonify([{"id": str(u.id), "email": u.email, "name": u.name} for u in users])


@app.route("/api/invite-accountant", methods=["POST"])
@login_required
@admin_required
def invite_accountant():
    """Pouze admin: vytvoří účetního, který spravuje směny tohoto účtu."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    if not email:
        return jsonify({"error": "E-mail je povinný"}), 400
    if len(password) < 6:
        return jsonify({"error": "Heslo musí mít alespoň 6 znaků"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Tento e-mail je již registrovaný"}), 400
    u = User(email=email, name=name or email.split("@")[0], role="ucetni", manages_user_id=current_user.id)
    u.password_hash = generate_password_hash(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({"ok": True, "message": f"Účetní {email} byl vytvořen. Může se přihlásit a spravovat směny."}), 201


@app.route("/api/employees/<int:eid>/create-access", methods=["POST"])
@login_required
@admin_required
def create_employee_access(eid):
    emp = Employee.query.join(Branch).filter(Branch.user_id == current_user.owner_id(), Employee.id == eid).first_or_404()
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or emp.email or "").strip().lower()
    password = data.get("password") or ""
    if not email:
        return jsonify({"error": "E-mail je povinný"}), 400
    if len(password) < 6:
        return jsonify({"error": "Heslo musí mít alespoň 6 znaků"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Tento e-mail je již používán"}), 400
    u = User(email=email, name=emp.name, role="employee", employee_id=emp.id)
    u.password_hash = generate_password_hash(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({"ok": True, "message": "Přístup vytvořen"}), 201


@app.route("/api/employees/<int:eid>", methods=["PATCH", "DELETE"])
@login_required
@admin_required
def employee(eid):
    e = Employee.query.join(Branch).filter(Branch.user_id == current_user.owner_id(), Employee.id == eid).first_or_404()
    if request.method == "DELETE":
        db.session.delete(e)
        db.session.commit()
        return "", 204
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    if "name" in data:
        e.name = data["name"]
    if "email" in data:
        e.email = data["email"]
    if "branchId" in data:
        e.branch_id = data["branchId"]
    if "hourlyRate" in data:
        r = data["hourlyRate"]
        e.hourly_rate = float(r) if r is not None and r != "" else None
    if "color" in data:
        color = (data.get("color") or "").strip() or None
        if color and not color.startswith("#"):
            color = "#" + color
        e.color = color[:8] if color else None
    db.session.commit()
    return jsonify(e.to_dict())


# ============ Presets ============
@app.route("/api/presets", methods=["GET"])
@login_required
@shift_manager_required
def list_presets():
    branch_id = request.args.get("branchId")
    q = ShiftPreset.query.filter(ShiftPreset.branch.has(user_id=current_user.owner_id()))
    if branch_id:
        q = q.filter(ShiftPreset.branch_id == branch_id)
    presets = q.all()
    return jsonify([p.to_dict() for p in presets])


@app.route("/api/presets", methods=["POST"])
@login_required
@shift_manager_required
def create_preset():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    branch_id = data.get("branchId")
    if not branch_id:
        return jsonify({"error": "Pobočka je povinná"}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Název presetu je povinný"}), 400
    branch = Branch.query.filter_by(id=branch_id, user_id=current_user.owner_id()).first_or_404()
    p = ShiftPreset(
        branch_id=branch.id, name=name,
        start_time=data["startTime"], end_time=data["endTime"],
        pinned=bool(data.get("pinned"))
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@app.route("/api/presets/<int:pid>", methods=["PATCH", "DELETE"])
@login_required
@shift_manager_required
def preset(pid):
    p = ShiftPreset.query.join(Branch).filter(Branch.user_id == current_user.owner_id(), ShiftPreset.id == pid).first_or_404()
    if request.method == "DELETE":
        db.session.delete(p)
        db.session.commit()
        return "", 204
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    if "name" in data:
        p.name = data["name"]
    if "startTime" in data:
        p.start_time = data["startTime"]
    if "endTime" in data:
        p.end_time = data["endTime"]
    if "pinned" in data:
        p.pinned = bool(data["pinned"])
    db.session.commit()
    return jsonify(p.to_dict())


# ============ Žádosti (volno, zpoždění) ============
LATE_TOLERANCE_MINUTES = 10  # Admin vidí jako "pozdě" až nad tuto hodnotu; zaměstnanec to nevidí


def _minutes_between_times(start_t, end_t):
    def parse(t):
        if not t:
            return 0
        parts = str(t).split(":")
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 else 0
    return parse(end_t) - parse(start_t)
@app.route("/api/my-branch-shifts", methods=["GET"])
@login_required
def my_branch_shifts():
    """Směny v pobočce zaměstnance – pro výběr u žádosti o výměnu (swap)."""
    if not current_user.employee_id:
        return jsonify([])
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify([])
    branch_id = current_user.employee.branch_id
    shifts = Shift.query.join(Employee).filter(
        Employee.branch_id == branch_id,
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).order_by(Shift.date, Shift.start_time).all()
    out = []
    for s in shifts:
        d = {"id": str(s.id), "date": s.date, "startTime": s.start_time, "endTime": s.end_time, "employeeId": str(s.employee_id), "employeeName": s.employee.name if s.employee else "?"}
        d["isMine"] = s.employee_id == current_user.employee_id
        out.append(d)
    return jsonify(out)


@app.route("/api/me/dashboard")
@login_required
def api_me_dashboard():
    """Přehled pro zaměstnance: pozdrav, dnešní směna, další směna, žádosti které se ho týkají."""
    if not current_user.employee_id:
        return jsonify({"employeeName": None, "todayShift": None, "nextShift": None, "requestsForMe": []})
    emp = current_user.employee
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    from datetime import timedelta
    end_date = (__import__("datetime").datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    my_shifts = Shift.query.filter(
        Shift.employee_id == current_user.employee_id,
        Shift.date >= today,
        Shift.date <= end_date
    ).order_by(Shift.date, Shift.start_time).all()
    today_shift = next((s for s in my_shifts if s.date == today), None)
    next_shift = next((s for s in my_shifts if s.date > today), None) if not today_shift else None
    branch_id = emp.branch_id
    reqs_for_me = []
    swap_reqs = EmployeeRequest.query.join(Shift, EmployeeRequest.other_shift_id == Shift.id).filter(
        EmployeeRequest.type_ == "swap",
        EmployeeRequest.status == "pending",
        Shift.employee_id == current_user.employee_id
    ).all()
    for r in swap_reqs:
        reqs_for_me.append(r.to_dict())
    cover_reqs = EmployeeRequest.query.join(Employee).filter(
        EmployeeRequest.type_ == "cover",
        EmployeeRequest.status == "pending",
        EmployeeRequest.employee_id != current_user.employee_id,
        Employee.branch_id == branch_id
    ).all()
    for r in cover_reqs:
        reqs_for_me.append(r.to_dict())
    def _shift_info(s):
        branch_name = (s.branch.name if s.branch else None) or (emp.branch.name if emp.branch else "")
        return {"date": s.date, "startTime": s.start_time, "endTime": s.end_time, "branchName": branch_name}
    return jsonify({
        "employeeName": emp.name,
        "todayShift": _shift_info(today_shift) if today_shift else None,
        "nextShift": _shift_info(next_shift) if next_shift else None,
        "requestsForMe": reqs_for_me,
    })


@app.route("/api/requests", methods=["GET"])
@login_required
def list_requests():
    if current_user.can_manage_shifts():
        branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
        if not branch_ids:
            return jsonify([])
        q = EmployeeRequest.query.join(Employee).filter(Employee.branch_id.in_(branch_ids))
        status = request.args.get("status")
        if status:
            q = q.filter(EmployeeRequest.status == status)
        reqs = q.order_by(EmployeeRequest.id.desc()).limit(150).all()
        out = []
        cover_apply_by_parent = {}
        for r in reqs:
            if r.type_ == "cover_apply" and r.applies_to_request_id:
                cover_apply_by_parent.setdefault(r.applies_to_request_id, []).append(r)
        for r in reqs:
            if r.type_ == "cover_apply":
                continue
            d = r.to_dict()
            if r.type_ == "cover":
                d["applications"] = [a.to_dict() for a in cover_apply_by_parent.get(r.id, [])]
            out.append(d)
        return jsonify(out)
    else:
        if not current_user.employee_id:
            return jsonify([])
        reqs = EmployeeRequest.query.filter_by(employee_id=current_user.employee_id).order_by(EmployeeRequest.id.desc()).all()
        return jsonify([r.to_dict() for r in reqs])


@app.route("/api/requests", methods=["POST"])
@login_required
def create_request():
    if not current_user.employee_id:
        return jsonify({"error": "Nemáte přiřazeného zaměstnance"}), 400
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Očekává se JSON"}), 400
    type_ = data.get("type")
    if type_ not in ("leave", "late", "swap", "cover", "cover_apply"):
        return jsonify({"error": "Neplatný typ žádosti (leave, late, swap, cover, cover_apply)"}), 400
    r = EmployeeRequest(employee_id=current_user.employee_id, type_=type_, status="pending")
    if type_ == "leave":
        r.date_from = (data.get("dateFrom") or "").strip()
        r.date_to = (data.get("dateTo") or r.date_from or "").strip()
        if not r.date_from:
            return jsonify({"error": "U volna zadejte datum od"}), 400
    elif type_ == "late":
        r.shift_date = data.get("shiftDate")
        try:
            r.shift_id = int(data["shiftId"]) if data.get("shiftId") else None
        except (TypeError, ValueError):
            r.shift_id = None
        r.planned_time = data.get("plannedTime")
        r.actual_time = data.get("actualTime")
        if r.planned_time and r.actual_time:
            mins = _minutes_between_times(r.planned_time, r.actual_time)
            r.minutes_late = max(0, mins)
    elif type_ == "swap":
        try:
            r.shift_id = int(data["shiftId"]) if data.get("shiftId") else None
            r.other_shift_id = int(data["otherShiftId"]) if data.get("otherShiftId") else None
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné ID směny"}), 400
        if not r.shift_id or not r.other_shift_id:
            return jsonify({"error": "U výměny vyberte obě směny"}), 400
        my_shift = Shift.query.join(Employee).filter(Shift.id == r.shift_id, Employee.branch_id == current_user.employee.branch_id, Shift.employee_id == current_user.employee_id).first()
        other = db.session.get(Shift, r.other_shift_id)
        if not my_shift or not other or other.employee_id == current_user.employee_id:
            return jsonify({"error": "Neplatné směny pro výměnu"}), 400
        if other.employee.branch_id != current_user.employee.branch_id:
            return jsonify({"error": "Směna musí být ze stejné pobočky"}), 400
    elif type_ == "cover":
        try:
            r.shift_id = int(data["shiftId"]) if data.get("shiftId") else None
        except (TypeError, ValueError):
            r.shift_id = None
        if not r.shift_id:
            return jsonify({"error": "Vyberte směnu"}), 400
        my_shift = Shift.query.filter(Shift.id == r.shift_id, Shift.employee_id == current_user.employee_id).first()
        if not my_shift:
            return jsonify({"error": "Neplatná směna"}), 400
    elif type_ == "cover_apply":
        try:
            r.applies_to_request_id = int(data["appliesToRequestId"]) if data.get("appliesToRequestId") else None
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná žádost o záskok"}), 400
        if not r.applies_to_request_id:
            return jsonify({"error": "Vyberte žádost o záskok"}), 400
        parent = db.session.get(EmployeeRequest, r.applies_to_request_id)
        if not parent or parent.type_ != "cover" or parent.status != "pending" or not parent.shift_id:
            return jsonify({"error": "Žádost o záskok není k dispozici"}), 400
        shift = db.session.get(Shift, parent.shift_id)
        if not shift or shift.employee.branch_id != current_user.employee.branch_id:
            return jsonify({"error": "Směna není ve vaší pobočce"}), 400
        if parent.employee_id == current_user.employee_id:
            return jsonify({"error": "Nemůžete se přihlásit na vlastní záskok"}), 400
        existing = EmployeeRequest.query.filter_by(
            applies_to_request_id=r.applies_to_request_id,
            employee_id=current_user.employee_id,
            status="pending"
        ).first()
        if existing:
            return jsonify({"error": "Už jste se na tento záskok přihlásili"}), 400
        r.shift_id = parent.shift_id
    r.note = data.get("note")
    db.session.add(r)
    db.session.commit()
    # Notifikace adminovi
    try:
        from mailer import notify_admin_new_request
        admin_user = r.employee.branch.user
        emp_name = r.employee.name
        type_labels = {"leave": "volno", "late": "zpoždění", "swap": "výměna směny", "cover": "záskok", "cover_apply": "přihláška na záskok"}
        if r.type_ == "leave":
            details = f"{r.date_from} – {r.date_to}"
        elif r.type_ == "late":
            details = f"{r.shift_date} plán {r.planned_time} → {r.actual_time or '?'}" + (f" (+{r.minutes_late} min)" if r.minutes_late else "")
        elif r.type_ == "swap" and r.shift and r.other_shift:
            details = f"má směnu {r.shift.date} {r.shift.start_time}–{r.shift.end_time}, chce vyměnit s {r.other_shift.employee.name} ({r.other_shift.date} {r.other_shift.start_time}–{r.other_shift.end_time})"
        elif r.type_ == "cover" and r.shift:
            details = f"nemůže na směnu {r.shift.date} {r.shift.start_time}–{r.shift.end_time}"
        elif r.type_ == "cover_apply" and r.applies_to_request_id and r.shift:
            parent_req = db.session.get(EmployeeRequest, r.applies_to_request_id)
            orig_name = parent_req.employee.name if parent_req and parent_req.employee else "?"
            details = f"chce zaskočit za {orig_name} na směnu {r.shift.date} {r.shift.start_time}–{r.shift.end_time}"
        else:
            details = r.note or "—"
        if os.environ.get("MAIL_DEBUG") == "1":
            import sys
            print(f"[mailer] Odesílám na admina: {admin_user.email}", file=sys.stderr)
        notify_admin_new_request(admin_user.email, emp_name, type_labels.get(r.type_, r.type_), details)
    except Exception as ex:
        import sys
        print(f"[mailer] Výjimka při notifikaci: {ex}", file=sys.stderr)
    return jsonify(r.to_dict()), 201


@app.route("/api/requests/<int:rid>", methods=["PATCH"])
@login_required
@shift_manager_required
def update_request(rid):
    req = EmployeeRequest.query.join(Employee).join(Branch).filter(
        Branch.user_id == current_user.owner_id(), EmployeeRequest.id == rid
    ).first_or_404()
    data = request.get_json(silent=True) or {}
    if "status" in data and data["status"] in ("approved", "rejected"):
        new_status = data["status"]
        req.status = new_status
        if new_status == "approved" and req.type_ == "swap" and req.shift_id and req.other_shift_id:
            s1 = db.session.get(Shift, req.shift_id)
            s2 = db.session.get(Shift, req.other_shift_id)
            if s1 and s2 and s1.employee_id == req.employee_id:
                emp1_id, emp2_id = s1.employee_id, s2.employee_id
                s1.employee_id, s2.employee_id = emp2_id, emp1_id
                db.session.flush()
                try:
                    from mailer import notify_employee_shift
                    for shift, emp_id in [(s1, emp2_id), (s2, emp1_id)]:
                        emp = db.session.get(Employee, emp_id)
                        if emp:
                            u = User.query.filter_by(employee_id=emp_id).first()
                            to_email = (u and u.email) or emp.email
                            if to_email:
                                notify_employee_shift(to_email, emp.name, shift.date, shift.start_time, shift.end_time, is_new=False)
                except Exception:
                    pass
        elif new_status == "approved" and req.type_ == "cover_apply" and req.shift_id and req.applies_to_request_id:
            parent = db.session.get(EmployeeRequest, req.applies_to_request_id)
            shift = db.session.get(Shift, req.shift_id)
            if parent and shift and parent.type_ == "cover" and shift.employee_id == parent.employee_id:
                shift.employee_id = req.employee_id
                parent.status = "approved"
                for other in EmployeeRequest.query.filter_by(applies_to_request_id=req.applies_to_request_id, status="pending").all():
                    if other.id != req.id:
                        other.status = "rejected"
                db.session.flush()
                try:
                    from mailer import notify_employee_shift
                    emp = db.session.get(Employee, req.employee_id)
                    if emp:
                        u = User.query.filter_by(employee_id=req.employee_id).first()
                        to_email = (u and u.email) or emp.email
                        if to_email:
                            notify_employee_shift(to_email, emp.name, shift.date, shift.start_time, shift.end_time, is_new=False)
                except Exception:
                    pass
        db.session.commit()
        # Notifikace zaměstnanci
        try:
            from mailer import notify_employee_request_resolved
            emp_user = User.query.filter_by(employee_id=req.employee_id).first()
            to_email = (emp_user and emp_user.email) or (req.employee and req.employee.email)
            if to_email:
                type_labels = {"leave": "volno", "late": "zpoždění", "swap": "výměna směny", "cover": "záskok", "cover_apply": "přihláška na záskok"}
                notify_employee_request_resolved(to_email, type_labels.get(req.type_, req.type_), new_status == "approved")
        except Exception:
            pass
    else:
        db.session.commit()
    return jsonify(req.to_dict())


# ============ Žádosti o registraci ============
@app.route("/api/registration-requests", methods=["GET"])
@login_required
@admin_required
def list_registration_requests():
    status = request.args.get("status", "pending")
    reqs = RegistrationRequest.query.filter_by(status=status).order_by(RegistrationRequest.id.desc()).limit(100).all()
    return jsonify([r.to_dict() for r in reqs])


@app.route("/api/registration-requests/<int:rid>/approve", methods=["POST"])
@login_required
@admin_required
def approve_registration(rid):
    import secrets
    from datetime import datetime, timedelta
    req = RegistrationRequest.query.filter_by(id=rid, status="pending").first_or_404()
    if User.query.filter_by(email=req.email).first():
        return jsonify({"error": "Uživatel s tímto e-mailem již existuje."}), 400
    # Zaměstnanec musí být v jedné z poboček admina (aby se zobrazil v kalendáři a seznamu zaměstnanců)
    data = request.get_json(silent=True) or {}
    branch_id_param = data.get("branchId")
    if branch_id_param is not None:
        bid, bid_err = _parse_branch_id(branch_id_param)
        if bid_err:
            return jsonify({"error": bid_err}), 400
        branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first()
        if not branch:
            return jsonify({"error": "Pobočka nenalezena."}), 404
    else:
        branch = Branch.query.filter_by(user_id=current_user.owner_id()).order_by(Branch.id).first()
    if not branch:
        return jsonify({"error": "Nejprve vytvořte alespoň jednu pobočku (Pobočky), pak schvalte registraci."}), 400
    # Vytvoř uživatele s dočasným heslem (nelze se přihlásit dokud nenastaví)
    temp_pass = secrets.token_urlsafe(32)
    user = User(email=req.email, name=req.name or req.email.split("@")[0], password_hash=generate_password_hash(temp_pass), role="employee")
    db.session.add(user)
    db.session.flush()
    emp = Employee(branch_id=branch.id, name=user.name or "Já", email=user.email)
    db.session.add(emp)
    db.session.flush()
    user.employee_id = emp.id
    token = secrets.token_urlsafe(32)
    req.status = "approved"
    req.approved_user_id = user.id
    req.token = token
    req.token_expires = (datetime.utcnow() + timedelta(days=7)).isoformat()[:19]
    db.session.commit()
    try:
        from mailer import notify_set_password_link
        # DŮLEŽITÉ: Použij APP_URL z .env – odkazy v e-mailu musí vést na veřejnou adresu
        # (127.0.0.1 na telefonu nejde otevřít!). Nastav např. APP_URL=https://vase-domena.cz
        base_url = (os.environ.get("APP_URL") or "").strip().rstrip("/") or request.host_url.rstrip("/")
        set_url = f"{base_url}{url_for('set_password', token=token)}"
        notify_set_password_link(req.email, req.name or req.email, set_url)
    except Exception as ex:
        import sys
        print(f"[mailer] Chyba odeslání: {ex}", file=sys.stderr)
    return jsonify(req.to_dict())


@app.route("/api/registration-requests/<int:rid>/reject", methods=["POST"])
@login_required
@admin_required
def reject_registration(rid):
    req = RegistrationRequest.query.filter_by(id=rid, status="pending").first_or_404()
    req.status = "rejected"
    db.session.commit()
    return jsonify(req.to_dict())


# ============ Žádosti o reset hesla ============
@app.route("/api/password-reset-requests", methods=["GET"])
@login_required
@admin_required
def list_password_reset_requests():
    status = request.args.get("status", "pending")
    reqs = PasswordResetRequest.query.filter_by(status=status).order_by(PasswordResetRequest.id.desc()).limit(100).all()
    return jsonify([r.to_dict() for r in reqs])


@app.route("/api/password-reset-requests/<int:rid>/approve", methods=["POST"])
@login_required
@admin_required
def approve_password_reset(rid):
    req = PasswordResetRequest.query.filter_by(id=rid, status="pending").first_or_404()
    user = req.user
    if not user:
        return jsonify({"error": "Uživatel nenalezen."}), 400
    try:
        _send_reset_password_email(user)
    except Exception as ex:
        return jsonify({"error": f"Nepodařilo se odeslat e-mail: {ex}"}), 500
    req.status = "approved"
    db.session.commit()
    return jsonify(req.to_dict())


@app.route("/api/password-reset-requests/<int:rid>/reject", methods=["POST"])
@login_required
@admin_required
def reject_password_reset(rid):
    req = PasswordResetRequest.query.filter_by(id=rid, status="pending").first_or_404()
    req.status = "rejected"
    db.session.commit()
    return jsonify(req.to_dict())


@app.route("/api/users/<int:uid>/send-reset-link", methods=["POST"])
@login_required
@admin_required
def send_user_reset_link(uid):
    """Admin manuálně odešle uživateli odkaz na reset hesla."""
    user = User.query.get_or_404(uid)
    if user.role == "ucetni" and user.manages_user_id != current_user.id:
        return jsonify({"error": "Můžete posílat reset jen svým účetním."}), 403
    try:
        _send_reset_password_email(user)
    except Exception as ex:
        return jsonify({"error": f"Nepodařilo se odeslat e-mail: {ex}"}), 500
    return jsonify({"ok": True, "message": f"Odkaz na reset hesla byl odeslán na {user.email}"})


# ============ Správa uživatelů (role) ============
@app.route("/api/users", methods=["GET"])
@login_required
@admin_required
def list_users():
    """Seznam všech uživatelů – pro úpravu rolí."""
    users = User.query.order_by(User.id).all()
    out = []
    for u in users:
        d = {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role or "admin", "employeeId": str(u.employee_id) if u.employee_id else None, "managesUserId": str(u.manages_user_id) if u.manages_user_id else None}
        if u.employee_id and u.employee:
            d["employee"] = u.employee.to_dict()
        out.append(d)
    return jsonify(out)


@app.route("/api/users/<int:uid>", methods=["PATCH"])
@login_required
@admin_required
def update_user(uid):
    """Úprava role a napojení uživatele."""
    if uid == current_user.id:
        return jsonify({"error": "Nemůžete měnit svou vlastní roli."}), 400
    user = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    if "role" in data:
        r = data["role"]
        if r in ("admin", "employee", "ucetni"):
            user.role = r
            if r != "ucetni":
                user.manages_user_id = None
            if r != "employee":
                user.employee_id = None
    if "managesUserId" in data:
        mid = data["managesUserId"]
        if mid is None or mid == "":
            user.manages_user_id = None
        else:
            mu = db.session.get(User, int(mid))
            if mu and mu.is_admin():
                user.manages_user_id = mu.id
    if "employeeId" in data:
        eid = data["employeeId"]
        if eid is None or eid == "":
            user.employee_id = None
        else:
            emp = db.session.get(Employee, int(eid))
            if emp:
                user.employee_id = emp.id
    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                return jsonify({"error": "E-mail je již používán jiným účtem"}), 400
            user.email = email
    if "name" in data:
        user.name = (data.get("name") or "").strip()
    db.session.commit()
    return jsonify({"id": str(user.id), "email": user.email, "name": user.name, "role": user.role, "employeeId": str(user.employee_id) if user.employee_id else None, "managesUserId": str(user.manages_user_id) if user.manages_user_id else None})


@app.route("/api/users/<int:uid>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(uid):
    """Smazání uživatele. Admin: smaže pobočky a zaměstnance. Jinak jen účet."""
    if uid == current_user.id:
        return jsonify({"error": "Nemůžete smazat sám sebe."}), 400
    user = User.query.get_or_404(uid)
    emp_ids = []
    for b in list(user.branches):
        emp_ids.extend([e.id for e in b.employees])
    for eid in emp_ids:
        EmployeeRequest.query.filter_by(employee_id=eid).delete()
        Shift.query.filter_by(employee_id=eid).delete()
        for u in User.query.filter_by(employee_id=eid).all():
            u.employee_id = None
    for b in list(user.branches):
        ShiftPreset.query.filter_by(branch_id=b.id).delete()
        for s in Shift.query.filter(Shift.branch_id == b.id).all():
            db.session.delete(s)
        for emp in list(b.employees):
            db.session.delete(emp)
        db.session.delete(b)
    PasswordResetToken.query.filter_by(user_id=user.id).delete()
    PasswordResetRequest.query.filter_by(user_id=user.id).delete()
    for r in RegistrationRequest.query.filter_by(approved_user_id=user.id).all():
        r.approved_user_id = None
    for u in User.query.filter_by(manages_user_id=user.id).all():
        u.manages_user_id = None
    db.session.delete(user)
    db.session.commit()
    return "", 204


# ============ Debug: test mailu ============
@app.route("/api/mail-test", methods=["POST"])
@login_required
@admin_required
def api_mail_test():
    """Pošle testovací mail na e-mail přihlášeného admina. Pro diagnostiku."""
    import smtplib
    from email.mime.text import MIMEText
    to = current_user.email
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    passwd = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    from_addr = os.environ.get("MAIL_FROM")
    if not all([host, user, passwd, from_addr]):
        return jsonify({
            "ok": False,
            "error": "Chybí SMTP konfigurace v .env",
            "SMTP_HOST": bool(host), "SMTP_USER": bool(user), "SMTP_PASS": bool(passwd), "MAIL_FROM": bool(from_addr)
        }), 500
    try:
        msg = MIMEText("Test – SMTP funguje.", "plain", "utf-8")
        msg["Subject"] = "Test – Vaping směnovač"
        msg["From"] = from_addr
        msg["To"] = to
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, passwd)
            smtp.sendmail(from_addr, to, msg.as_string())
        return jsonify({"ok": True, "message": f"Testovací mail odeslán na {to}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ============ Admin přehled ============
@app.route("/api/overview")
@login_required
@shift_manager_required
def api_overview():
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    pending = EmployeeRequest.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids), EmployeeRequest.status == "pending"
    ).count()
    today_shifts = Shift.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids), Shift.date == today
    ).count()
    employees_count = Employee.query.filter(Employee.branch_id.in_(branch_ids)).count()
    branches_count = len(branch_ids)
    return jsonify({
        "pendingRequests": pending,
        "todayShifts": today_shifts,
        "employeesCount": employees_count,
        "branchesCount": branches_count,
    })


@app.route("/api/stats/late-overview")
@login_required
@shift_manager_required
def api_late_overview():
    """Přehled zpoždění – kolikrát byl každý zaměstnanec pozdě (>10 min tolerance)."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify({"byEmployee": []})
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
    reqs = EmployeeRequest.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids),
        EmployeeRequest.type_ == "late",
        EmployeeRequest.status.in_(["approved", "pending"]),
        EmployeeRequest.shift_date >= from_date,
        EmployeeRequest.shift_date <= to_date,
        EmployeeRequest.minutes_late != None,
        EmployeeRequest.minutes_late > LATE_TOLERANCE_MINUTES,
    ).order_by(EmployeeRequest.shift_date.desc()).all()
    by_emp = {}
    for r in reqs:
        eid = r.employee_id
        if eid not in by_emp:
            by_emp[eid] = {"employee": r.employee.to_dict(), "count": 0, "incidents": []}
        by_emp[eid]["count"] += 1
        by_emp[eid]["incidents"].append({
            "date": r.shift_date,
            "minutesLate": r.minutes_late,
            "plannedTime": r.planned_time,
            "actualTime": r.actual_time,
        })
    return jsonify({
        "byEmployee": [{"employee": v["employee"], "lateCount": v["count"], "incidents": v["incidents"][:10]} for v in by_emp.values()],
        "toleranceMinutes": LATE_TOLERANCE_MINUTES,
    })


# ============ Kalendář – měsíční data (1 request) ============
@app.route("/api/calendar/month", methods=["GET"])
@login_required
def api_calendar_month():
    """
    Vrací všechna data pro vykreslení kalendáře na daný měsíc.
    Parametry: month=YYYY-MM, branchId (pro admina povinné, pro zaměstnance se použije jeho pobočka).

    Struktura odpovědi:
    {
      "month": "YYYY-MM",
      "firstDate": "YYYY-MM-DD",
      "lastDate": "YYYY-MM-DD",
      "shifts": [
        {
          "id", "date", "startTime", "endTime", "note", "branchId",
          "employeeId", "employeeName", "employeeColor",
          "hourlyRate"  // sazba použité pro směnu (employee nebo branch default)
        }
      ],
      "employees": [{"id", "name", "color", "branchId"}],
      "presets": [{"id", "name", "startTime", "endTime", "branchId"}]
    }
    """
    from datetime import datetime, timedelta
    from calendar import monthrange

    month_str = request.args.get("month")
    branch_id_param = request.args.get("branchId")

    if not month_str or len(month_str) != 7:
        return jsonify({"error": "Chybí nebo neplatný parametr month (YYYY-MM)"}), 400

    try:
        y, m = map(int, month_str.split("-"))
        first = datetime(y, m, 1).date()
        last_day = monthrange(y, m)[1]
        last = datetime(y, m, last_day).date()
        first_str = first.strftime("%Y-%m-%d")
        last_str = last.strftime("%Y-%m-%d")
    except (ValueError, KeyError):
        return jsonify({"error": "Neplatný formát měsíce (YYYY-MM)"}), 400

    if current_user.is_employee():
        emp = db.session.get(Employee, current_user.employee_id) if current_user.employee_id else None
        branch_id = emp.branch_id if emp else None
    else:
        try:
            branch_id = int(branch_id_param) if branch_id_param else None
        except (TypeError, ValueError):
            branch_id = None
        if not branch_id:
            branches = Branch.query.filter_by(user_id=current_user.owner_id()).first()
            branch_id = branches.id if branches else None
        if branch_id:
            b = Branch.query.filter_by(id=branch_id, user_id=current_user.owner_id()).first()
            if not b:
                return jsonify({"error": "Pobočka nenalezena"}), 404

    if not branch_id:
        payload = {"month": month_str, "firstDate": first_str, "lastDate": last_str, "shifts": [], "employees": [], "presets": [], "coverage": {}, "openTime": None, "closeTime": None}
        return jsonify(payload), 200, {"Cache-Control": "no-cache, no-store, must-revalidate"}

    branch = Branch.query.filter_by(id=branch_id).first()

    def _open_close_for_date(date_str):
        from datetime import datetime
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        wd = d.weekday()
        if wd >= 5 and branch.open_time_weekend and branch.close_time_weekend:
            return branch.open_time_weekend, branch.close_time_weekend
        return branch.open_time or "08:00", branch.close_time or "20:00"

    # Shifts pro pobočku v měsíci
    shifts = Shift.query.join(Employee).filter(
        or_(Shift.branch_id == branch_id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch_id)),
        Shift.date >= first_str,
        Shift.date <= last_str,
    ).order_by(Shift.date, Shift.start_time).all()

    # Employees pobočky
    employees = Employee.query.filter_by(branch_id=branch_id).all()

    # Presets pobočky
    presets = ShiftPreset.query.filter_by(branch_id=branch_id).all()

    shifts_data = []
    for s in shifts:
        emp = s.employee
        hr = emp.get_hourly_rate() if emp else None
        shifts_data.append({
            "id": str(s.id),
            "date": s.date,
            "startTime": s.start_time,
            "endTime": s.end_time,
            "note": s.note,
            "branchId": str(s.branch_id or branch_id),
            "employeeId": str(emp.id) if emp else None,
            "employeeName": emp.name if emp else "—",
            "employeeColor": emp.color if emp and emp.color else None,
            "hourlyRate": float(hr) if hr is not None else None,
        })

    # Coverage (pokrytí otevírací doby) pro každý den – víkend má jinou dobu
    from coverage import _time_to_minutes, _compute_coverage_gaps
    by_date = {}
    for s in shifts:
        if s.date not in by_date:
            by_date[s.date] = []
        by_date[s.date].append(s)
    coverage = {}
    for d in range(last_day):
        date_str = (first + timedelta(days=d)).strftime("%Y-%m-%d")
        ot, ct = _open_close_for_date(date_str)
        open_min = _time_to_minutes(ot)
        close_min = _time_to_minutes(ct)
        shift_list = by_date.get(date_str, [])
        intervals = [(_time_to_minutes(s.start_time), _time_to_minutes(s.end_time)) for s in shift_list]
        gaps = _compute_coverage_gaps(open_min, close_min, intervals)
        coverage[date_str] = len(gaps) == 0

    payload = {
        "month": month_str,
        "firstDate": first_str,
        "lastDate": last_str,
        "shifts": shifts_data,
        "employees": [{"id": str(e.id), "name": e.name, "color": e.color, "branchId": str(e.branch_id)} for e in employees],
        "presets": [{"id": str(p.id), "name": p.name, "startTime": p.start_time, "endTime": p.end_time, "branchId": str(p.branch_id)} for p in presets],
        "coverage": coverage,
        "openTime": branch.open_time or "08:00",
        "closeTime": branch.close_time or "20:00",
        "openTimeWeekend": branch.open_time_weekend,
        "closeTimeWeekend": branch.close_time_weekend,
    }
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    return jsonify(payload), 200, headers


# ============ My shifts (aggregated) ============
@app.route("/api/my-shifts", methods=["GET"])
@login_required
def list_my_shifts():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify([])
    if current_user.is_employee():
        shifts = Shift.query.filter(
            Shift.employee_id == current_user.employee_id,
            Shift.date >= from_date,
            Shift.date <= to_date
        ).order_by(Shift.date, Shift.start_time).all()
    else:
        branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
        shifts = Shift.query.join(Employee).filter(
            Employee.branch_id.in_(branch_ids),
            Shift.date >= from_date,
            Shift.date <= to_date
        ).order_by(Shift.date, Shift.start_time).all()
    return jsonify([s.to_dict() for s in shifts])


# ============ Shifts ============
@app.route("/api/shifts", methods=["GET"])
@login_required
@shift_manager_required
def list_shifts():
    branch_id = request.args.get("branchId")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not branch_id or not from_date or not to_date:
        return jsonify([])
    shifts = Shift.query.join(Employee).join(Branch).filter(
        Branch.user_id == current_user.owner_id(),
        Employee.branch_id == branch_id,
        Shift.date >= from_date,
        Shift.date <= to_date
    ).all()
    return jsonify([s.to_dict() for s in shifts])


# ============ Validace směn ============
def _api_error(code, message, details=None):
    """Vrátí JSON chyby ve formátu { error: { code, message, details } }."""
    payload = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def _validate_shift_times(start_time, end_time):
    """
    Ověří, že end_time > start_time (směna v rámci jednoho dne, přes půlnoc ZAKÁZÁNO).
    Vrátí (ok, error_response, status_code) – při chybě (False, jsonify(...), 400).
    """
    start_min = _time_to_minutes(start_time)
    end_min = _time_to_minutes(end_time)
    if start_min >= end_min:
        return False, jsonify(_api_error(
            "INVALID_TIME_RANGE",
            "Konec směny musí být po začátku. Směny přes půlnoc nejsou povoleny.",
            {"startTime": start_time, "endTime": end_time}
        )), 400
    return True, None, None


def _check_shift_overlap(employee_id, date, start_time, end_time, exclude_shift_id=None):
    """
    Zkontroluje překryv směn pro zaměstnance ve stejném dni.
    Vrátí (ok, overlapping_shift) – při konfliktu (False, existing_shift).
    """
    existing = Shift.query.filter(
        Shift.employee_id == employee_id,
        Shift.date == date,
    )
    if exclude_shift_id is not None:
        existing = existing.filter(Shift.id != exclude_shift_id)
    existing = existing.all()
    start_min = _time_to_minutes(start_time)
    end_min = _time_to_minutes(end_time)
    for s in existing:
        s_start = _time_to_minutes(s.start_time)
        s_end = _time_to_minutes(s.end_time)
        if start_min < s_end and s_start < end_min:  # intervals overlap
            return False, s
    return True, None


def _validate_employee_branch(employee, branch_id):
    """
    Zaměstnanec musí být přiřazen ke stejné pobočce jako směna.
    branch_id může být None (= použije se pobočka zaměstnance).
    Vrátí (ok, error_response, status_code) – při chybě (False, jsonify(...), 400).
    """
    emp_branch = employee.branch_id
    effective_branch = branch_id if branch_id is not None else emp_branch
    if effective_branch != emp_branch:
        return False, jsonify(_api_error(
            "EMPLOYEE_BRANCH_MISMATCH",
            "Zaměstnanec musí být přiřazen k pobočce směny.",
            {"employeeBranchId": str(emp_branch), "shiftBranchId": str(branch_id) if branch_id else "null"}
        )), 400
    return True, None, None


@app.route("/api/shifts/copy", methods=["POST"])
@login_required
@shift_manager_required
def copy_shifts():
    """
    Kopírování rozpisů. Vstup: sourceRange {from,to}, targetRange {from,to}, branchId,
    preserveAssignment (bool), defaultEmployeeId (když preserveAssignment=false).
    Transakční: buď vše, nebo nic. Při konfliktech vrací 409 s detailním seznamem.
    """
    from datetime import datetime, timedelta

    data = request.get_json(silent=True)
    if not data:
        return jsonify(_api_error("INVALID_REQUEST", "Očekává se JSON")), 400

    src = data.get("sourceRange") or {}
    tgt = data.get("targetRange") or {}
    src_from = src.get("from")
    src_to = src.get("to")
    tgt_from = tgt.get("from")
    tgt_to = tgt.get("to")
    branch_id = data.get("branchId")
    preserve = data.get("preserveAssignment", True)
    default_emp_id = data.get("defaultEmployeeId")
    on_conflict = data.get("onConflict", "abort")  # "abort" = vrátit 409, "skip" = přeskočit konfliktní a vytvořit zbytek

    if not all([src_from, src_to, tgt_from, tgt_to, branch_id]):
        return jsonify(_api_error("INVALID_REQUEST", "Chybí sourceRange.from/to, targetRange.from/to nebo branchId")), 400

    try:
        branch_id_int = int(branch_id)
    except (TypeError, ValueError):
        return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID pobočky")), 400
    branch = Branch.query.filter_by(id=branch_id_int, user_id=current_user.owner_id()).first()
    if not branch:
        return jsonify(_api_error("BRANCH_NOT_FOUND", "Pobočka nenalezena")), 404

    try:
        d1 = datetime.strptime(src_from, "%Y-%m-%d").date()
        d2 = datetime.strptime(src_to, "%Y-%m-%d").date()
        d3 = datetime.strptime(tgt_from, "%Y-%m-%d").date()
        d4 = datetime.strptime(tgt_to, "%Y-%m-%d").date()
    except ValueError:
        return jsonify(_api_error("INVALID_REQUEST", "Neplatný formát data (YYYY-MM-DD)")), 400

    if d1 > d2 or d3 > d4:
        return jsonify(_api_error("INVALID_REQUEST", "Zdrojové a cílové rozsahy musí být od-do v pořádku")), 400

    src_days = (d2 - d1).days + 1
    tgt_days = (d4 - d3).days + 1
    if src_days != tgt_days:
        return jsonify(_api_error("INVALID_REQUEST", "Zdrojový a cílový rozsah musí mít stejný počet dní")), 400

    if not preserve and not default_emp_id:
        return jsonify(_api_error("INVALID_REQUEST", "Při nezachování přiřazení je nutné vybrat výchozího zaměstnance")), 400

    default_emp = None
    if not preserve and default_emp_id:
        try:
            default_emp_id_int = int(default_emp_id)
        except (TypeError, ValueError):
            return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID zaměstnance")), 400
        default_emp = Employee.query.join(Branch).filter(
            Branch.user_id == current_user.owner_id(),
            Employee.id == default_emp_id_int,
            Employee.branch_id == branch.id,
        ).first()
        if not default_emp:
            return jsonify(_api_error("EMPLOYEE_NOT_FOUND", "Výchozí zaměstnanec nenalezen nebo není v pobočce")), 404

    # Načíst zdrojové směny – 1 dotaz
    shifts = Shift.query.join(Employee).filter(
        or_(Shift.branch_id == branch.id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch.id)),
        Shift.date >= src_from,
        Shift.date <= src_to,
    ).order_by(Shift.date, Shift.start_time).all()

    # Mapování datumů: src_from+i -> tgt_from+i
    date_map = {}
    for i in range(src_days):
        sd = (d1 + timedelta(days=i)).strftime("%Y-%m-%d")
        td = (d3 + timedelta(days=i)).strftime("%Y-%m-%d")
        date_map[sd] = td

    # Sestavit nové směny a validovat konflikty
    to_create = []
    conflicts = []

    for s in shifts:
        target_date = date_map.get(s.date)
        if not target_date:
            continue
        emp_id = s.employee_id if preserve else default_emp.id
        emp = s.employee if preserve else default_emp
        ok, conflicting = _check_shift_overlap(
            emp_id, target_date, s.start_time, s.end_time, exclude_shift_id=None
        )
        if not ok:
            conflicts.append({
                "employeeName": emp.name,
                "date": target_date,
                "startTime": s.start_time,
                "endTime": s.end_time,
                "existingShift": {"startTime": conflicting.start_time, "endTime": conflicting.end_time} if conflicting else None,
            })
            continue
        ok, _, _ = _validate_employee_branch(emp, branch.id)
        if not ok:
            conflicts.append({"employeeName": emp.name, "date": target_date, "startTime": s.start_time, "endTime": s.end_time, "reason": "Zaměstnanec není v pobočce"})
            continue
        to_create.append({
            "employee_id": emp_id,
            "branch_id": branch.id,
            "date": target_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "preset_id": s.preset_id,
            "note": s.note,
        })

    preview = data.get("preview", False)
    if preview:
        return jsonify({
            "preview": True,
            "sourceShiftCount": len(shifts),
            "count": len(to_create),
            "conflicts": conflicts,
            "skippedCount": len(conflicts),
            "canProceed": len(conflicts) == 0,
        })

    if conflicts and on_conflict != "skip":
        return jsonify(_api_error(
            "COPY_CONFLICTS",
            "Kopie by vytvořila konflikty se stávajícími směnami.",
            {"conflicts": conflicts}
        )), 409

    if not to_create:
        skipped_msg = f" ({len(conflicts)} přeskočeno – konflikt)" if conflicts else ""
        return jsonify({"copied": 0, "skipped": len(conflicts), "message": "Žádné směny ke zkopírování" + skipped_msg}), 200

    # Transakční vytvoření
    try:
        for item in to_create:
            s = Shift(**item)
            db.session.add(s)
        db.session.commit()
        _invalidate_coverage_cache()
        skipped = len(conflicts)
        msg = f"Zkopírováno {len(to_create)} směn"
        if skipped:
            msg += f", {skipped} přeskočeno (konflikt)"
        return jsonify({"copied": len(to_create), "skipped": skipped, "message": msg}), 201
    except Exception:
        db.session.rollback()
        return jsonify(_api_error("COPY_FAILED", "Chyba při ukládání kopií")), 500


@app.route("/api/shifts", methods=["POST"])
@login_required
@shift_manager_required
def create_shift():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(_api_error("INVALID_REQUEST", "Očekává se JSON")), 400
    try:
        emp_id = int(data["employeeId"]) if isinstance(data.get("employeeId"), str) else data.get("employeeId")
        if emp_id is None:
            return jsonify(_api_error("INVALID_REQUEST", "Chybí zaměstnanec")), 400
    except (TypeError, ValueError):
        return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID zaměstnance")), 400
    emp = Employee.query.join(Branch).filter(Branch.user_id == current_user.owner_id(), Employee.id == emp_id).first_or_404()
    branch_id = data.get("branchId")
    if branch_id is not None:
        try:
            bid = int(branch_id) if isinstance(branch_id, str) else branch_id
        except (TypeError, ValueError):
            return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID pobočky")), 400
        b = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first()
        branch_id = bid if b else None
    if branch_id is None:
        branch_id = emp.branch_id

    ok, err, status = _validate_employee_branch(emp, branch_id)
    if not ok:
        return err, status

    start_time = data.get("startTime", "08:00")
    end_time = data.get("endTime", "14:00")
    ok, err, status = _validate_shift_times(start_time, end_time)
    if not ok:
        return err, status

    overlap_ok, conflicting = _check_shift_overlap(
        emp.id, data["date"], start_time, end_time, exclude_shift_id=None
    )
    if not overlap_ok:
        return jsonify(_api_error(
            "SHIFT_OVERLAP",
            "Zaměstnanec má v tento den již jinou směnu, která se s touto překrývá.",
            {"existingShift": {"id": str(conflicting.id), "startTime": conflicting.start_time, "endTime": conflicting.end_time}}
        )), 409

    s = Shift(
        employee_id=emp.id, branch_id=branch_id, date=data["date"],
        start_time=start_time, end_time=end_time,
        preset_id=data.get("presetId"), note=data.get("note")
    )
    db.session.add(s)
    db.session.commit()
    _invalidate_coverage_cache()
    return jsonify(s.to_dict()), 201


@app.route("/api/shifts/<int:sid>", methods=["PATCH", "DELETE"])
@login_required
@shift_manager_required
def shift(sid):
    s = Shift.query.join(Employee).join(Branch).filter(Branch.user_id == current_user.owner_id(), Shift.id == sid).first_or_404()
    if request.method == "DELETE":
        db.session.delete(s)
        db.session.commit()
        _invalidate_coverage_cache()
        return "", 204
    data = request.get_json(silent=True)
    if not data:
        return jsonify(_api_error("INVALID_REQUEST", "Očekává se JSON")), 400

    if "employeeId" in data:
        try:
            emp_id = int(data["employeeId"]) if isinstance(data["employeeId"], str) else data["employeeId"]
        except (TypeError, ValueError):
            return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID zaměstnance")), 400
        emp = Employee.query.join(Branch).filter(Branch.user_id == current_user.owner_id(), Employee.id == emp_id).first_or_404()
        s.employee_id = emp.id
    else:
        emp = s.employee

    branch_id = s.branch_id
    if "branchId" in data:
        bid = data["branchId"]
        if bid is not None:
            try:
                bid_int = int(bid) if isinstance(bid, str) else bid
            except (TypeError, ValueError):
                return jsonify(_api_error("INVALID_REQUEST", "Neplatné ID pobočky")), 400
            b = Branch.query.filter_by(id=bid_int, user_id=current_user.owner_id()).first()
            branch_id = b.id if b else emp.branch_id
        else:
            branch_id = emp.branch_id
        s.branch_id = branch_id

    if "date" in data:
        s.date = data["date"]
    if "startTime" in data:
        s.start_time = data["startTime"]
    if "endTime" in data:
        s.end_time = data["endTime"]
    if "presetId" in data:
        s.preset_id = data["presetId"]
    if "note" in data:
        s.note = data["note"]

    ok, err, status = _validate_employee_branch(emp, s.branch_id)
    if not ok:
        return err, status

    ok, err, status = _validate_shift_times(s.start_time, s.end_time)
    if not ok:
        return err, status

    overlap_ok, conflicting = _check_shift_overlap(
        s.employee_id, s.date, s.start_time, s.end_time, exclude_shift_id=s.id
    )
    if not overlap_ok:
        return jsonify(_api_error(
            "SHIFT_OVERLAP",
            "Zaměstnanec má v tento den již jinou směnu, která se s touto překrývá.",
            {"existingShift": {"id": str(conflicting.id), "startTime": conflicting.start_time, "endTime": conflicting.end_time}}
        )), 409

    db.session.commit()
    _invalidate_coverage_cache()
    try:
        from mailer import notify_employee_shift
        emp = s.employee
        emp_user = User.query.filter_by(employee_id=emp.id).first()
        to_email = (emp_user and emp_user.email) or emp.email
        if to_email:
            notify_employee_shift(to_email, emp.name, s.date, s.start_time, s.end_time, is_new=False)
        elif os.environ.get("MAIL_DEBUG") == "1":
            print(f"[mailer] Směna pro {emp.name} – neodesláno, zaměstnanec nemá e-mail", file=__import__("sys").stderr)
    except Exception:
        pass
    return jsonify(s.to_dict())


@app.route("/api/send-schedule-emails", methods=["POST"])
@login_required
@shift_manager_required
def send_schedule_emails():
    """Odešle zaměstnancům e-mail s rozpisem směn. Parametry: from, to (YYYY-MM-DD)."""
    data = request.get_json(silent=True) or {}
    from_date = (data.get("from") or "").strip()
    to_date = (data.get("to") or "").strip()
    if not from_date or not to_date:
        return jsonify({"error": "Chybí parametry from a to (YYYY-MM-DD)"}), 400
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
    shifts = Shift.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids),
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).order_by(Shift.date, Shift.start_time).all()
    by_employee = {}
    for s in shifts:
        eid = s.employee_id
        if eid not in by_employee:
            by_employee[eid] = {"employee": s.employee, "shifts": []}
        by_employee[eid]["shifts"].append(s)
    sent = 0
    for eid, data_emp in by_employee.items():
        emp = data_emp["employee"]
        emp_user = User.query.filter_by(employee_id=emp.id).first()
        to_email = (emp_user and emp_user.email) or emp.email
        if not to_email:
            continue
        rows = []
        for s in data_emp["shifts"]:
            parts = str(s.date).split("-")
            date_fmt = f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else s.date
            rows.append(f"<tr style='border-bottom:1px solid #e5e7eb'><td style='padding:0.5rem'>{date_fmt}</td><td style='padding:0.5rem'>{s.start_time}–{s.end_time}</td></tr>")
        table_html = f"""
        <table style="border-collapse:collapse;width:100%;max-width:320px;margin:1rem 0;border:1px solid #e5e7eb;border-radius:0.5rem;overflow:hidden">
          <thead><tr style="background:#2563eb;color:white"><th style="padding:0.5rem;text-align:left">Datum</th><th style="padding:0.5rem">Čas</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        """
        try:
            from mailer import notify_employee_schedule
            notify_employee_schedule(to_email, emp.name, table_html, from_date, to_date)
            sent += 1
        except Exception:
            pass
    return jsonify({"ok": True, "message": f"Rozpis odeslán {sent} zaměstnancům."})


# ============ Stats ============
def _minutes_between(start_t, end_t):
    def parse(t):
        if not t:
            return 0
        parts = str(t).split(":")
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) >= 2 else 0

    return parse(end_t) - parse(start_t)


@app.route("/api/stats/hours", methods=["GET"])
@login_required
def stats_hours():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify([])
    if current_user.is_employee():
        shifts = Shift.query.filter(
            Shift.employee_id == current_user.employee_id,
            Shift.date >= from_date,
            Shift.date <= to_date,
        ).all()
        by_emp = {}
        for s in shifts:
            mid = s.employee_id
            if mid not in by_emp:
                emp = s.employee
                by_emp[mid] = {"name": emp.name, "minutes": 0, "employee": emp}
            by_emp[mid]["minutes"] += max(0, _minutes_between(s.start_time, s.end_time))
        out = []
        for eid, data in by_emp.items():
            total = data["minutes"]
            h, mn = divmod(total, 60)
            hours_decimal = total / 60.0
            rate = data["employee"].get_hourly_rate()
            estimated_pay = round(hours_decimal * rate, 2) if rate else None
            out.append({
                "employeeId": str(eid),
                "name": data["name"],
                "minutes": total,
                "hoursFormatted": f"{h}:{mn:02d}" if mn else str(h),
                "hourlyRate": rate,
                "estimatedPay": estimated_pay,
            })
        return jsonify(out)
    branch_id = request.args.get("branchId")
    if not branch_id:
        return jsonify([])
    bid, bid_err = _parse_branch_id(branch_id)
    if bid_err:
        return jsonify({"error": bid_err}), 400
    branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    # Směny na této pobočce: shift.branch_id == branch NEBO (branch_id null a employee tam patří)
    shifts = Shift.query.join(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.user_id == current_user.owner_id(),
        Shift.date >= from_date,
        Shift.date <= to_date,
        or_(Shift.branch_id == branch.id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch.id)),
    ).all()
    by_emp = {}
    for s in shifts:
        mid = s.employee_id
        if mid not in by_emp:
            emp = s.employee
            by_emp[mid] = {"name": emp.name, "minutes": 0, "employee": emp}
        by_emp[mid]["minutes"] += max(0, _minutes_between(s.start_time, s.end_time))
    out = []
    for eid, data in by_emp.items():
        total = data["minutes"]
        h, mn = divmod(total, 60)
        hours_decimal = total / 60.0
        rate = data["employee"].get_hourly_rate()
        estimated_pay = round(hours_decimal * rate, 2) if rate else None
        out.append({
            "employeeId": str(eid),
            "name": data["name"],
            "minutes": total,
            "hoursFormatted": f"{h}:{mn:02d}" if mn else str(h),
            "hourlyRate": rate,
            "estimatedPay": estimated_pay,
        })
    return jsonify(out)


@app.route("/api/stats/hours-overview", methods=["GET"])
@login_required
@shift_manager_required
def stats_hours_overview():
    """Přehled hodin pro účetního – všechny pobočky, zaměstnanci a jejich hodiny.
    Každý řádek = zaměstnanec + pobočka (připraveno na budoucí podporu více poboček na zaměstnance)."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify({"rows": [], "branches": []})
    if current_user.is_employee():
        return jsonify({"rows": [], "branches": []})
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
    if not branch_ids:
        return jsonify({"rows": [], "branches": []})
    shifts = Shift.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids),
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).all()
    # Skupování: (employee_id, branch_id) -> minuty; branch_id = shift.branch_id pokud nastaveno, jinak employee.branch_id
    by_key = {}
    branches_by_id = {b.id: b for b in Branch.query.filter(Branch.id.in_(branch_ids)).all()}
    for s in shifts:
        bid = s.branch_id if s.branch_id is not None and s.branch_id in branches_by_id else s.employee.branch_id
        eid = s.employee_id
        key = (eid, bid)
        if key not in by_key:
            emp = s.employee
            branch = branches_by_id.get(bid) or (emp.branch if emp else None)
            by_key[key] = {"employeeId": emp.id, "name": emp.name, "branchId": bid, "branchName": branch.name if branch else "?", "minutes": 0, "employee": emp}
        by_key[key]["minutes"] += max(0, _minutes_between(s.start_time, s.end_time))
    rows = []
    branches = {b.id: b for b in Branch.query.filter(Branch.id.in_(branch_ids)).all()}
    for key, data in by_key.items():
        total = data["minutes"]
        h, mn = divmod(total, 60)
        hours_decimal = total / 60.0
        rate = data["employee"].get_hourly_rate()
        estimated_pay = round(hours_decimal * rate, 2) if rate else None
        rows.append({
            "employeeId": str(data["employeeId"]),
            "name": data["name"],
            "branchId": str(data["branchId"]),
            "branchName": data["branchName"],
            "minutes": total,
            "hoursFormatted": f"{h}:{mn:02d}" if mn else str(h),
            "hourlyRate": rate,
            "estimatedPay": estimated_pay,
        })
    rows.sort(key=lambda r: (r["branchName"], r["name"]))
    branch_list = Branch.query.filter(Branch.id.in_(branch_ids)).order_by(Branch.name).all()
    return jsonify({"rows": rows, "branches": [{"id": str(b.id), "name": b.name} for b in branch_list]})


@app.route("/api/stats/who-with-whom", methods=["GET"])
@login_required
@shift_manager_required
def stats_who_with_whom():
    branch_id = request.args.get("branchId")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not branch_id or not from_date or not to_date:
        return jsonify({"byDate": {}})
    branch = Branch.query.filter_by(id=branch_id, user_id=current_user.owner_id()).first_or_404()
    shifts = Shift.query.join(Employee).filter(
        Employee.branch_id == branch.id,
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).order_by(Shift.date, Shift.start_time).all()
    by_date = {}
    for s in shifts:
        if s.date not in by_date:
            by_date[s.date] = []
        overlaps = []
        for o in shifts:
            if o.date == s.date and o.id != s.id:
                if s.start_time < o.end_time and o.start_time < s.end_time:
                    overlaps.append(o.employee.name if o.employee else "?")
        by_date[s.date].append({
            "employeeId": str(s.employee_id),
            "employeeName": s.employee.name if s.employee else "?",
            "startTime": s.start_time,
            "endTime": s.end_time,
            "overlapsWith": overlaps,
        })
    return jsonify({"byDate": by_date})


# ============ Kontrola pokrytí dne ============
def _time_to_minutes(t):
    """'08:30' -> 510"""
    if not t:
        return 0
    parts = str(t).split(":")
    return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)


def _minutes_to_time(m):
    """510 -> '08:30'"""
    h, mn = divmod(m, 60)
    return f"{h:02d}:{mn:02d}"


def _compute_coverage_gaps(open_min, close_min, shifts):
    """Vrátí mezery v pokrytí. shifts = [(start_min, end_min), ...]."""
    if open_min >= close_min:
        return []  # neplatná otevírací doba
    intervals = []
    for s in shifts:
        start_min = max(s[0], open_min)
        end_min = min(s[1], close_min)
        if start_min < end_min:
            intervals.append((start_min, end_min))
    if not intervals:
        return [(_minutes_to_time(open_min), _minutes_to_time(close_min))]
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for a, b in intervals[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    gaps = []
    if merged[0][0] > open_min:
        gaps.append((_minutes_to_time(open_min), _minutes_to_time(merged[0][0])))
    for i in range(len(merged) - 1):
        gaps.append((_minutes_to_time(merged[i][1]), _minutes_to_time(merged[i + 1][0])))
    if merged[-1][1] < close_min:
        gaps.append((_minutes_to_time(merged[-1][1]), _minutes_to_time(close_min)))
    return gaps


@app.route("/api/coverage", methods=["GET"])
@login_required
@shift_manager_required
def api_coverage():
    """Kontrola pokrytí otevírací doby směnami. Parametry: branchId, date."""
    branch_id = request.args.get("branchId")
    date = request.args.get("date")
    if not branch_id or not date:
        return jsonify({"error": "Chybí branchId nebo date"}), 400
    bid, bid_err = _parse_branch_id(branch_id)
    if bid_err:
        return jsonify({"error": bid_err}), 400
    branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    open_t = branch.open_time or "08:00"
    close_t = branch.close_time or "20:00"
    open_min = _time_to_minutes(open_t)
    close_min = _time_to_minutes(close_t)
    shifts = Shift.query.join(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.user_id == current_user.owner_id(),
        Shift.date == date,
        or_(Shift.branch_id == branch.id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch.id)),
    ).all()
    shift_intervals = [(_time_to_minutes(s.start_time), _time_to_minutes(s.end_time)) for s in shifts]
    gaps = _compute_coverage_gaps(open_min, close_min, shift_intervals)
    # Segmenty s počtem lidí: sweep line
    events = []
    for a, b in shift_intervals:
        a, b = max(a, open_min), min(b, close_min)
        if a < b:
            events.append((a, 1))
            events.append((b, -1))
    events.sort(key=lambda x: (x[0], -x[1]))
    segments_with_count = []
    count = 0
    seg_start = None
    for t, delta in events:
        if seg_start is not None and t > seg_start and count > 0:
            segments_with_count.append({"from": _minutes_to_time(seg_start), "to": _minutes_to_time(t), "count": count})
        count += delta
        if count > 0 and seg_start is None:
            seg_start = t
        elif count == 0:
            seg_start = None
    return jsonify({
        "branchId": str(branch.id),
        "branchName": branch.name,
        "date": date,
        "openTime": open_t,
        "closeTime": close_t,
        "fullyCovered": len(gaps) == 0,
        "gaps": [{"from": g[0], "to": g[1]} for g in gaps],
        "segments": segments_with_count,
        "shifts": [{"id": str(s.id), "employeeName": s.employee.name if s.employee else "?", "startTime": s.start_time, "endTime": s.end_time} for s in shifts],
    })


@app.route("/api/coverage/auto", methods=["GET"])
@login_required
@shift_manager_required
def api_coverage_auto():
    """Automatická kontrola pokrytí. Parametry: month=YYYY-MM (celý měsíc) nebo days=N (dnes+zítra)."""
    from datetime import datetime, timedelta
    from calendar import monthrange

    month_str = request.args.get("month")
    owner_id = current_user.owner_id()
    cache_key = f"{owner_id}:{month_str}" if month_str else None

    if month_str:
        # Optimalizovaná cesta: 2 dotazy (pobočky + směny), cache per měsíc
        if cache_key and cache_key in _coverage_cache:
            return jsonify(_coverage_cache[cache_key])

        data = compute_coverage_month(Branch, Shift, Employee, owner_id, month_str)
        if data is None:
            return jsonify({"error": "Neplatný formát měsíce (YYYY-MM)"}), 400

        resp = coverage_month_to_grid_response(data)
        if cache_key:
            _coverage_cache[cache_key] = resp
        return jsonify(resp)

    # Fallback: days=N – jednoduchý výpočet pro několik dní
    try:
        days = min(int(request.args.get("days", 2)), 31)
    except (TypeError, ValueError):
        days = 2
    today = datetime.now().date()
    dates = [(today + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(days)]
    # Pro days používáme stejný výpočet – určíme span měsíců a načteme
    if not dates:
        return jsonify({"dates": [], "grid": [], "alerts": []})
    first_d, last_d = dates[0], dates[-1]
    branches = list(Branch.query.filter_by(user_id=owner_id).order_by(Branch.name).all())
    branch_ids = [b.id for b in branches]
    if not branch_ids:
        return jsonify({"dates": dates, "grid": [], "alerts": []})

    shifts = Shift.query.join(Employee).filter(
        or_(
            Shift.branch_id.in_(branch_ids),
            and_(Shift.branch_id.is_(None), Employee.branch_id.in_(branch_ids)),
        ),
        Shift.date >= first_d,
        Shift.date <= last_d,
    ).order_by(Shift.date, Shift.start_time).all()

    from coverage import _time_to_minutes, _compute_coverage_gaps, _effective_branch_id

    by_branch_date = {bid: {d: [] for d in dates} for bid in branch_ids}
    for s in shifts:
        bid = _effective_branch_id(s)
        if bid and bid in by_branch_date and s.date in by_branch_date[bid]:
            by_branch_date[bid][s.date].append(s)

    grid = []
    alerts = []
    for branch in branches:
        bid = branch.id
        open_t = branch.open_time or "08:00"
        close_t = branch.close_time or "20:00"
        open_min = _time_to_minutes(open_t)
        close_min = _time_to_minutes(close_t)
        row = {"branchId": str(bid), "branchName": branch.name, "days": {}}
        day_shifts = by_branch_date.get(bid, {})
        for date in dates:
            shift_list = day_shifts.get(date, [])
            intervals = [(_time_to_minutes(s.start_time), _time_to_minutes(s.end_time)) for s in shift_list]
            gaps = _compute_coverage_gaps(open_min, close_min, intervals)
            shifts_data = [{"employeeName": s.employee.name if s.employee else "?", "startTime": s.start_time, "endTime": s.end_time} for s in shift_list]
            cov = {"covered": len(gaps) == 0, "gaps": [{"from": g[0], "to": g[1]} for g in gaps], "openTime": open_t, "closeTime": close_t, "shifts": shifts_data}
            row["days"][date] = cov
            if not cov["covered"]:
                alerts.append({"branchId": str(bid), "branchName": branch.name, "date": date, "openTime": open_t, "closeTime": close_t, "gaps": cov["gaps"]})
        grid.append(row)
    return jsonify({"dates": dates, "grid": grid, "alerts": alerts})


# ============ Export ============
def _fmt_filename_date(date_str):
    """2026-02-01 -> 01.02.2026"""
    if not date_str or len(str(date_str)) < 10:
        return date_str or ""
    parts = str(date_str).split("-")
    return f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 else date_str


def _stream_csv(rows, filename):
    from urllib.parse import quote
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    for row in rows:
        writer.writerow([str(cell) for cell in row])
    # RFC 5987: filename*=UTF-8''percent-encoded – zajišťuje ASCII v headeru
    disp = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": disp},
    )


@app.route("/api/export/shifts", methods=["GET"])
@login_required
@shift_manager_required
def export_shifts():
    branch_id = request.args.get("branchId")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not branch_id or not from_date or not to_date:
        return jsonify({"error": "Chybí parametry"}), 400
    bid, bid_err = _parse_branch_id(branch_id)
    if bid_err:
        return jsonify({"error": bid_err}), 400
    branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    shifts = Shift.query.join(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.user_id == current_user.owner_id(),
        Shift.date >= from_date,
        Shift.date <= to_date,
        or_(Shift.branch_id == branch.id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch.id)),
    ).order_by(Shift.date, Shift.start_time).all()
    rows = [["Datum", "Zaměstnanec", "Od", "Do", "Poznámka"]]
    for s in shifts:
        rows.append([s.date, s.employee.name if s.employee else "?", s.start_time, s.end_time, s.note or ""])
    return _stream_csv(rows, f"směny_{_fmt_filename_date(from_date)}_{_fmt_filename_date(to_date)}.csv")


@app.route("/api/export/hours", methods=["GET"])
@login_required
@shift_manager_required
def export_hours():
    branch_id = request.args.get("branchId")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not branch_id or not from_date or not to_date:
        return jsonify({"error": "Chybí parametry"}), 400
    bid, bid_err = _parse_branch_id(branch_id)
    if bid_err:
        return jsonify({"error": bid_err}), 400
    branch = Branch.query.filter_by(id=bid, user_id=current_user.owner_id()).first_or_404()
    shifts = Shift.query.join(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.user_id == current_user.owner_id(),
        Shift.date >= from_date,
        Shift.date <= to_date,
        or_(Shift.branch_id == branch.id, and_(Shift.branch_id.is_(None), Employee.branch_id == branch.id)),
    ).all()
    by_emp = {}
    for s in shifts:
        mid = s.employee_id
        if mid not in by_emp:
            by_emp[mid] = {"name": s.employee.name if s.employee else "?", "minutes": 0, "employee": s.employee}
        by_emp[mid]["minutes"] += max(0, _minutes_between(s.start_time, s.end_time))
    rows = [["Zaměstnanec", "Hodiny", "Hodinová sazba (Kč)", "Orientační plat (Kč)"]]
    for eid, data in by_emp.items():
        total = data["minutes"]
        h, mn = divmod(total, 60)
        hours_str = f"{h}:{mn:02d}" if mn else str(h)
        rate = data["employee"].get_hourly_rate() if data.get("employee") else None
        hours_dec = total / 60.0
        pay = round(hours_dec * rate, 2) if rate else ""
        rate_str = str(rate) if rate else ""
        pay_str = str(pay) if pay else ""
        rows.append([data["name"], hours_str, rate_str, pay_str])
    return _stream_csv(rows, f"hodiny_{_fmt_filename_date(from_date)}_{_fmt_filename_date(to_date)}.csv")


@app.route("/api/export/hours-overview", methods=["GET"])
@login_required
@shift_manager_required
def export_hours_overview():
    """Export přehledu hodin (všechny pobočky) – pro účetního."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify({"error": "Chybí from a to"}), 400
    if current_user.is_employee():
        return jsonify({"error": "Přístup jen pro admina/účetního"}), 403
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
    shifts = Shift.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids),
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).all()
    branches_by_id = {b.id: b for b in Branch.query.filter(Branch.id.in_(branch_ids)).all()}
    by_key = {}
    for s in shifts:
        bid = s.branch_id if s.branch_id is not None and s.branch_id in branches_by_id else (s.employee.branch_id if s.employee else None)
        eid = s.employee_id
        key = (eid, bid)
        if key not in by_key:
            emp = s.employee
            branch = branches_by_id.get(bid) or (emp.branch if emp else None)
            by_key[key] = {"name": emp.name if emp else "?", "branchName": branch.name if branch else "?", "minutes": 0, "employee": emp}
        by_key[key]["minutes"] += max(0, _minutes_between(s.start_time, s.end_time))
    rows = [["Zaměstnanec", "Pobočka", "Hodiny", "Hodinová sazba (Kč)", "Orientační plat (Kč)"]]
    for (eid, bid), data in sorted(by_key.items(), key=lambda x: (x[1]["branchName"], x[1]["name"])):
        total = data["minutes"]
        h, mn = divmod(total, 60)
        hours_str = f"{h}:{mn:02d}" if mn else str(h)
        rate = data["employee"].get_hourly_rate() if data.get("employee") else None
        hours_dec = total / 60.0
        pay = round(hours_dec * rate, 2) if rate else ""
        rate_str = str(rate) if rate else ""
        pay_str = str(pay) if pay else ""
        rows.append([data["name"], data["branchName"], hours_str, rate_str, pay_str])
    return _stream_csv(rows, f"hodiny_prehled_{_fmt_filename_date(from_date)}_{_fmt_filename_date(to_date)}.csv")


def _ical_shifts_for_user(user, from_date, to_date):
    """Vrátí směny pro uživatele v rozsahu datumů."""
    if user.is_employee() and user.employee_id:
        return Shift.query.filter(
            Shift.employee_id == user.employee_id,
            Shift.date >= from_date,
            Shift.date <= to_date,
        ).order_by(Shift.date, Shift.start_time).all()
    branch_ids = [b.id for b in Branch.query.filter_by(user_id=user.owner_id()).all()]
    return Shift.query.join(Employee).filter(
        Employee.branch_id.in_(branch_ids),
        Shift.date >= from_date,
        Shift.date <= to_date,
    ).order_by(Shift.date, Shift.start_time).all()


@app.route("/api/export/ical", methods=["GET"])
def export_ical():
    """iCal export – s tokenem (odběr) nebo přihlášením."""
    from datetime import datetime, timedelta
    token = request.args.get("token")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if token:
        user = User.query.filter_by(ical_token=token).first()
        if not user:
            return jsonify({"error": "Neplatný token"}), 404
        if not from_date or not to_date:
            today = datetime.now().strftime("%Y-%m-%d")
            from_date = today
            to_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        if not current_user.is_authenticated:
            return jsonify({"error": "Přihlaste se nebo použijte odkaz s tokenem"}), 401
        if not from_date or not to_date:
            return jsonify({"error": "Chybí from a to"}), 400
        user = current_user
    shifts = _ical_shifts_for_user(user, from_date, to_date)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Vaping směnovač//CS"]
    for s in shifts:
        def _ical_time(t):
            p = (t or "08:00").split(":")
            return f"{int(p[0]):02d}{int(p[1]) if len(p) > 1 else 0:02d}00"
        dt_start = f"{s.date.replace('-','')}T{_ical_time(s.start_time)}"
        dt_end = f"{s.date.replace('-','')}T{_ical_time(s.end_time)}"
        summary = f"Směna: {s.employee.name if s.employee else '?'}"
        lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:{summary}",
            f"UID:shift-{s.id}@smenovac",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines).encode("utf-8")
    fn = f"smeny_{_fmt_filename_date(from_date)}_{_fmt_filename_date(to_date)}.ics"
    return Response(
        body,
        mimetype="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"},
    )


@app.route("/export/pdf")
@login_required
def export_pdf_page():
    """Stránka pro tisk/tisk do PDF – rozvrh směn."""
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        from_date = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        to_date = from_date
    if current_user.is_employee():
        shifts = Shift.query.filter(
            Shift.employee_id == current_user.employee_id,
            Shift.date >= from_date,
            Shift.date <= to_date,
        ).order_by(Shift.date, Shift.start_time).all()
    else:
        branch_ids = [b.id for b in Branch.query.filter_by(user_id=current_user.owner_id()).all()]
        shifts = Shift.query.join(Employee).filter(
            Employee.branch_id.in_(branch_ids),
            Shift.date >= from_date,
            Shift.date <= to_date,
        ).order_by(Shift.date, Shift.start_time).all()
    by_date = {}
    for s in shifts:
        if s.date not in by_date:
            by_date[s.date] = []
        by_date[s.date].append(s)
    from_date_fmt = _fmt_filename_date(from_date)
    to_date_fmt = _fmt_filename_date(to_date)
    return render_template("export_pdf.html", shifts=shifts, by_date=by_date, from_date=from_date_fmt, to_date=to_date_fmt)


# ============ Init ============
with app.app_context():
    init_db()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    # Pokud je nastaveno APP_URL (např. na síťovou IP), poslouchej na všech rozhraních
    host = "0.0.0.0" if os.environ.get("APP_URL") else "127.0.0.1"
    app.run(debug=debug, host=host, port=port)
