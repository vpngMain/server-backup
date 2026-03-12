"""Centrální auth systém: API + admin web."""
import os
from datetime import datetime
from flask import Flask, redirect, url_for, request, session, flash
from models import db, User, SSOToken, UserAllowedApp
from api.routes import api_bp
from admin.routes import admin_bp

app = Flask(__name__)


def _router_url():
    url = os.environ.get("ROUTER_URL", "").strip()
    if url:
        return url.rstrip("/")
    try:
        from urllib.parse import urlparse
        p = urlparse(request.url_root)
        return f"{p.scheme}://{p.hostname}" if p.port in (80, 8000, None) else f"{p.scheme}://{p.hostname}:8000"
    except Exception:
        return "http://localhost:8000"


@app.context_processor
def inject_router_url():
    theme_viktorinka = False
    uid = session.get("admin_user_id")
    if uid:
        user = User.query.get(uid)
        if user and getattr(user, "username", None):
            theme_viktorinka = (str(user.username).strip().lower() == "viktorinka")
    return {"router_url": _router_url(), "theme_viktorinka": theme_viktorinka}


@app.route("/")
def index():
    return redirect(url_for("admin.login"))


@app.route("/auth/sso")
def auth_sso():
    """SSO ze Směrosu: ověření tokenu a přihlášení do admin rozhraní (pouze admin)."""
    token = (request.args.get("token") or "").strip()
    if not token:
        flash("Chybí SSO token.", "error")
        return redirect(url_for("admin.login"))
    sso = SSOToken.query.filter_by(token=token, used=False).first()
    if not sso:
        flash("Neplatný nebo již použitý SSO token.", "error")
        return redirect(url_for("admin.login"))
    if datetime.utcnow() > sso.expires_at:
        sso.used = True
        db.session.commit()
        flash("SSO token vypršel.", "error")
        return redirect(url_for("admin.login"))
    user = User.find_by_username(sso.username)
    if not user or not user.is_admin:
        sso.used = True
        db.session.commit()
        flash("Přístup jen pro administrátory.", "error")
        return redirect(url_for("admin.login"))
    sso.used = True
    db.session.commit()
    session["admin_user_id"] = user.id
    return redirect(url_for("admin.dashboard"))


app.config.from_object("config")
db.init_app(app)

app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)


with app.app_context():
    db.create_all()
    # První admin, pokud v DB není žádný uživatel (jméno: admin, PIN: 1234 – po přihlášení změňte)
    if User.query.count() == 0:
        admin = User(username="admin", role="admin", active=True)
        admin.set_pin("1234")
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
