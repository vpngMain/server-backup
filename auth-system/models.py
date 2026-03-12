"""Modely centrální databáze uživatelů."""
from datetime import datetime
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Branch(db.Model):
    """Pobočka – centrální seznam, používá se v aplikacích (Odběros, Objednávač, DPD)."""
    __tablename__ = "branches"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=True, default="")

    def __repr__(self):
        return f"<Branch {self.name}>"


class Warehouse(db.Model):
    """Sklad – centrální seznam pro Objednávač (pobočky = Branch, sklady = Warehouse)."""
    __tablename__ = "warehouses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=True, default="")

    def __repr__(self):
        return f"<Warehouse {self.name}>"


user_branches = db.Table(
    "user_branches",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("branch_id", db.Integer, db.ForeignKey("branches.id"), primary_key=True),
)

# Kódy aplikací na směrovači (co může admin uživateli povolit)
ROUTER_APP_CODES = ("odberos", "objednavac", "dpd")


class UserAllowedApp(db.Model):
    """Povolené aplikace na směrovači pro daného uživatele (odberos, objednavac, dpd)."""
    __tablename__ = "user_allowed_apps"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    app_code = db.Column(db.String(20), primary_key=True)


class User(db.Model):
    """Centrální uživatel: username + PIN, role, branch (řetězec zpětně kompat.). M:N branches."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # admin | user
    branch = db.Column(db.String(100), nullable=True)  # název pobočky (zpětná kompat.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True, nullable=False)
    # Pro Objednávač: volitelné
    objednavac_role = db.Column(db.String(20), nullable=True)  # admin | branch | warehouse
    warehouse = db.Column(db.String(100), nullable=True)  # název skladu

    branches = db.relationship(
        "Branch",
        secondary=user_branches,
        backref=db.backref("users", lazy="dynamic"),
        lazy="dynamic",
    )
    # Povolené aplikace na směrovači (odberos, objednavac, dpd) – admin vidí všechno včetně Správy
    allowed_app_codes = db.relationship(
        "UserAllowedApp",
        backref="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def get_allowed_app_codes(self):
        """Seznam kódů aplikací, které uživatel uvidí na směrovači. Admin vidí vše (včetně auth)."""
        if self.role == "admin":
            return list(ROUTER_APP_CODES) + ["auth"]
        try:
            codes = [a.app_code for a in self.allowed_app_codes.all()]
        except Exception:
            return list(ROUTER_APP_CODES)
        if not codes:
            return list(ROUTER_APP_CODES)
        return codes

    @classmethod
    def find_by_username(cls, username, *, active_only=True):
        """Vyhledá uživatele podle jména (case-insensitive)."""
        if not username or not isinstance(username, str):
            return None
        uname = username.strip()
        if not uname:
            return None
        q = cls.query.filter(func.lower(cls.username) == uname.lower())
        if active_only:
            q = q.filter(cls.active.is_(True))
        return q.first()

    def set_pin(self, pin: str) -> None:
        self.pin_hash = generate_password_hash(pin, method="pbkdf2:sha256")

    def check_pin(self, pin: str) -> bool:
        return bool(pin and check_password_hash(self.pin_hash, pin))

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.username}>"


class LoginLog(db.Model):
    """Log přihlášení: login_time, username, ip, application."""
    __tablename__ = "login_log"
    id = db.Column(db.Integer, primary_key=True)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    username = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(45), nullable=True)
    application = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<LoginLog {self.username} @ {self.login_time}>"


class SSOToken(db.Model):
    """Jednorázový token pro SSO z Směrosu do podaplikací."""
    __tablename__ = "sso_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<SSOToken {self.username}>"
