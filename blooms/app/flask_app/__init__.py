"""Flask aplikace – přihlášení přes Flask-Login (session do souborů v instance/flask_session)."""
import tempfile
from pathlib import Path

from flask import Flask, g
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from app.config import (
    BASE_DIR,
    SECRET_KEY,
    USE_TABULATOR,
    COMPANY_NAME,
    COMPANY_STREET,
    COMPANY_CITY,
    COMPANY_ZIP,
    COMPANY_COUNTRY,
    COMPANY_ICO,
    COMPANY_DIC,
    COMPANY_PHONE,
    COMPANY_EMAIL,
)
from app.db import SessionLocal
from app.models import User
from app.services.company_profile_service import load_company_profile


def _is_writable_dir(path: Path) -> bool:
    """Ověří zapisovatelnost adresáře vytvořením dočasného souboru."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="wtest_", dir=str(path))
        Path(tmp_name).unlink(missing_ok=True)
        return fd >= 0
    except Exception:
        return False


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "app" / "templates"),
        static_folder=str(BASE_DIR / "app" / "static") if (BASE_DIR / "app" / "static").exists() else None,
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["USE_TABULATOR"] = USE_TABULATOR
    app.config["COMPANY_NAME"] = COMPANY_NAME
    app.config["COMPANY_STREET"] = COMPANY_STREET
    app.config["COMPANY_CITY"] = COMPANY_CITY
    app.config["COMPANY_ZIP"] = COMPANY_ZIP
    app.config["COMPANY_COUNTRY"] = COMPANY_COUNTRY
    app.config["COMPANY_ICO"] = COMPANY_ICO
    app.config["COMPANY_DIC"] = COMPANY_DIC
    app.config["COMPANY_PHONE"] = COMPANY_PHONE
    app.config["COMPANY_EMAIL"] = COMPANY_EMAIL
    csrf = CSRFProtect(app)

    # Server-side session do souborů (přežije restart serveru).
    # Když adresář není zapisovatelný (časté na serveru), fallback na cookie session.
    session_dir = BASE_DIR / "instance" / "flask_session"
    if _is_writable_dir(session_dir):
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_FILE_DIR"] = str(session_dir)
        try:
            from flask_session import Session
            Session(app)
        except ImportError:
            pass
    else:
        print(
            f"[WARN] Session dir není zapisovatelný: {session_dir}. "
            "Používám fallback na cookie session.",
            flush=True,
        )

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Přihlášení vyžadováno."

    @app.before_request
    def before_request():
        g.db = SessionLocal()

    @app.after_request
    def log_request(response):
        from flask import request
        loc = response.headers.get("Location", "")
        if response.status_code == 302 and loc and "empty_path" in loc:
            loc = loc.replace("error=empty_path", "error=no_files")
            response.headers["Location"] = loc
        extra = f" -> {loc}" if response.status_code == 302 and loc else ""
        print(f"  {request.method} {request.path} -> {response.status_code}{extra}", flush=True)
        return response

    @login_manager.user_loader
    def load_user(user_id: str):
        """Načte uživatele – volá se až po before_request, takže g.db je nastavené."""
        try:
            return g.db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
        except (ValueError, TypeError):
            return None

    @app.teardown_request
    def teardown_request(exc=None):
        db = getattr(g, "db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_template_vars():
        from flask import request
        company_profile = load_company_profile(app.config)
        return {
            "dev_skip_auth": False,
            "query_error": request.args.get("error"),
            "use_tabulator": USE_TABULATOR,
            "company_profile": company_profile,
        }

    @app.template_filter("czech_date")
    def czech_date_filter(val):
        """Formát data pro češtinu: 10. 3. 2026."""
        if val is None:
            return ""
        return f"{val.day}. {val.month}. {val.year}"

    @app.template_filter("price2")
    def price2_filter(val):
        """Formát ceny na 4 desetinná místa pro zobrazení."""
        if val is None:
            return ""
        try:
            from decimal import Decimal
            d = Decimal(str(val))
            return f"{float(d):.4f}"
        except Exception:
            return str(val)

    from app.flask_app.auth import auth_bp
    from app.flask_app.main import main_bp
    from app.flask_app.products import products_bp
    from app.flask_app.customers import customers_bp
    from app.flask_app.delivery import delivery_bp
    from app.flask_app.import_routes import import_bp
    from app.flask_app.users import users_bp

    # Login/logout endpointy často padají na CSRF při reverse proxy / restartu session.
    # Pro interní app je bezpečnější mít plynulý login bez hard 400.
    csrf.exempt(auth_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(delivery_bp, url_prefix="/delivery")
    app.register_blueprint(import_bp, url_prefix="/import")
    app.register_blueprint(users_bp, url_prefix="/users")

    from app.flask_app.errors import register_error_handlers
    register_error_handlers(app)

    return app
