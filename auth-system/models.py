"""Modely centrální databáze uživatelů."""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Centrální uživatel: username + PIN, role, branch. Volitelně objednavac_role a warehouse."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # admin | user
    branch = db.Column(db.String(100), nullable=True)  # název pobočky
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True, nullable=False)
    # Pro Objednávač: volitelné
    objednavac_role = db.Column(db.String(20), nullable=True)  # admin | branch | warehouse
    warehouse = db.Column(db.String(100), nullable=True)  # název skladu

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
