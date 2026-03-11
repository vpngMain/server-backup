from datetime import date, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Nominály v Kč – Obálka (jen bankovky)
OBALKA_DENOMINATIONS = [5000, 2000, 1000, 500, 200, 100]

# Nominály v Kč – Kasička (bankovky + mince)
KASA_DENOMINATIONS = [5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2, 1]


def week_start(d: date) -> date:
    """Pondělí daného týdne (ISO týden)."""
    return d - timedelta(days=d.weekday())


def week_end(d: date) -> date:
    """Neděle daného týdne."""
    return week_start(d) + timedelta(days=6)


def datum_splatnosti(d: date) -> date:
    """Středa daného týdne."""
    return week_start(d) + timedelta(days=2)


class Branch(db.Model):
    __tablename__ = "branch"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), default="")

    users = db.relationship("User", backref="branch", lazy=True)
    entries = db.relationship("Entry", backref="branch", lazy=True)

    def __repr__(self):
        return f"<Branch {self.name}>"


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' | 'admin'
    created_at = db.Column(db.DateTime, default=db.func.now())

    entries = db.relationship("Entry", backref="user", lazy=True)

    def set_pin(self, pin: str) -> None:
        self.pin_hash = generate_password_hash(pin, method="pbkdf2:sha256")

    def check_pin(self, pin: str) -> bool:
        return bool(pin and check_password_hash(self.pin_hash, pin))

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.name}>"


class Entry(db.Model):
    __tablename__ = "entry"
    __table_args__ = (
        db.UniqueConstraint("branch_id", "datum", name="uq_entry_branch_datum"),
        db.Index("ix_entry_branch_tyden", "branch_id", "tyden_zacatek"),
    )
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branch.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    datum = db.Column(db.Date, nullable=False)
    datum_splatnosti = db.Column(db.Date, nullable=False)
    tyden_zacatek = db.Column(db.Date, nullable=False)
    tyden_konec = db.Column(db.Date, nullable=False)
    k_zaplaceni = db.Column(db.Numeric(12, 2), nullable=True)

    # Obálka (6 nominálů)
    obalka_5000 = db.Column(db.Integer, default=0)
    obalka_2000 = db.Column(db.Integer, default=0)
    obalka_1000 = db.Column(db.Integer, default=0)
    obalka_500 = db.Column(db.Integer, default=0)
    obalka_200 = db.Column(db.Integer, default=0)
    obalka_100 = db.Column(db.Integer, default=0)

    # Kasička (13 nominálů)
    kasa_5000 = db.Column(db.Integer, default=0)
    kasa_2000 = db.Column(db.Integer, default=0)
    kasa_1000 = db.Column(db.Integer, default=0)
    kasa_500 = db.Column(db.Integer, default=0)
    kasa_200 = db.Column(db.Integer, default=0)
    kasa_100 = db.Column(db.Integer, default=0)
    kasa_50 = db.Column(db.Integer, default=0)
    kasa_20 = db.Column(db.Integer, default=0)
    kasa_10 = db.Column(db.Integer, default=0)
    kasa_5 = db.Column(db.Integer, default=0)
    kasa_2 = db.Column(db.Integer, default=0)
    kasa_1 = db.Column(db.Integer, default=0)

    OBALKA_COLS = ["obalka_5000", "obalka_2000", "obalka_1000", "obalka_500", "obalka_200", "obalka_100"]
    KASA_COLS = [
        "kasa_5000", "kasa_2000", "kasa_1000", "kasa_500", "kasa_200", "kasa_100",
        "kasa_50", "kasa_20", "kasa_10", "kasa_5", "kasa_2", "kasa_1",
    ]

    def celkem_obalka(self) -> int:
        total = 0
        for col, denom in zip(self.OBALKA_COLS, OBALKA_DENOMINATIONS):
            total += (getattr(self, col) or 0) * denom
        return total

    def celkem_kasa(self) -> int:
        total = 0
        for col, denom in zip(self.KASA_COLS, KASA_DENOMINATIONS):
            total += (getattr(self, col) or 0) * denom
        return total

    def obalka_dict(self):
        return {str(d): getattr(self, c) or 0 for c, d in zip(self.OBALKA_COLS, OBALKA_DENOMINATIONS)}

    def kasa_dict(self):
        return {str(d): getattr(self, c) or 0 for c, d in zip(self.KASA_COLS, KASA_DENOMINATIONS)}

    def __repr__(self):
        return f"<Entry branch={self.branch_id} datum={self.datum}>"
