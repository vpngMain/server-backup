"""SQLite databáze – modely pro směny."""
from sqlalchemy import text, Index
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="admin", nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id", use_alter=True, name="fk_user_employee"), nullable=True)
    manages_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # účetní spravuje data tohoto admina
    ical_token = db.Column(db.String(64), unique=True, nullable=True)  # pro odběr kalendáře bez přihlášení

    employee = db.relationship("Employee", backref="user", uselist=False)

    def is_admin(self):
        return self.role == "admin"

    def is_accountant(self):
        return self.role == "ucetni" and self.manages_user_id is not None

    def is_employee(self):
        return self.role == "employee" and self.employee_id is not None

    def owner_id(self):
        """ID uživatele, jehož data zobrazujeme (admin = sám sobě, účetní = svému adminovi)."""
        return self.manages_user_id if self.is_accountant() else self.id

    def can_manage_shifts(self):
        """Může spravovat směny: admin, účetní, nebo vlastník poboček (fallback při nesprávné roli)."""
        if self.is_admin() or self.is_accountant():
            return True
        # Fallback: vlastní pobočky = má práva na správu (oprava nesprávně nastavené role)
        return Branch.query.filter_by(user_id=self.id).count() > 0

    def is_full_admin(self):
        """Plný admin – může zakládat pobočky, mazat zaměstnance, vytvářet přístupy."""
        return self.is_admin()


class Branch(db.Model):
    __tablename__ = "branches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(512))
    default_hourly_rate = db.Column(db.Numeric(10, 2), default=None)
    open_time = db.Column(db.String(5), default="08:00")  # otevírací doba např. 08:00
    close_time = db.Column(db.String(5), default="20:00")  # zavírací doba např. 20:00
    open_time_weekend = db.Column(db.String(5), default=None)  # víkend – když None, použije se open_time
    close_time_weekend = db.Column(db.String(5), default=None)  # víkend – když None, použije se close_time

    user = db.relationship("User", backref="branches")
    employees = db.relationship("Employee", backref="branch", cascade="all, delete-orphan")
    presets = db.relationship("ShiftPreset", backref="branch", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "address": self.address,
            "defaultHourlyRate": float(self.default_hourly_rate) if self.default_hourly_rate is not None else None,
            "openTime": self.open_time or "08:00",
            "closeTime": self.close_time or "20:00",
            "openTimeWeekend": self.open_time_weekend,
            "closeTimeWeekend": self.close_time_weekend,
            "_count": {"employees": len(self.employees), "presets": len(self.presets)},
        }


class Employee(db.Model):
    __tablename__ = "employees"
    __table_args__ = (Index("ix_employees_branch_id", "branch_id"),)
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    hourly_rate = db.Column(db.Numeric(10, 2), default=None)
    color = db.Column(db.String(7), nullable=True)  # hex např. #2563eb

    shifts = db.relationship("Shift", backref="employee", cascade="all, delete-orphan")

    def get_hourly_rate(self):
        if self.hourly_rate is not None:
            return float(self.hourly_rate)
        if not self.branch:
            return None
        return float(self.branch.default_hourly_rate) if self.branch.default_hourly_rate is not None else None

    def to_dict(self):
        branch_data = None
        if self.branch:
            branch_data = {"id": str(self.branch.id), "name": self.branch.name, "defaultHourlyRate": float(self.branch.default_hourly_rate) if self.branch.default_hourly_rate is not None else None}
        return {
            "id": str(self.id),
            "name": self.name,
            "email": self.email,
            "hourlyRate": float(self.hourly_rate) if self.hourly_rate is not None else None,
            "color": self.color,
            "branch": branch_data,
        }


class ShiftPreset(db.Model):
    __tablename__ = "shift_presets"
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.String(5), default="08:00")
    end_time = db.Column(db.String(5), default="14:00")
    pinned = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "branchId": str(self.branch_id),
            "pinned": self.pinned,
        }


class PasswordResetToken(db.Model):
    """Token pro reset hesla – platí 1 hodinu. Vytváří se při schválení žádosti nebo manuálně z adminu."""
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.String(30), nullable=False)

    user = db.relationship("User", backref="password_reset_tokens")


class PasswordResetRequest(db.Model):
    """Žádost o reset hesla – uživatel požádal na stránce, admin schválí/zamítne."""
    __tablename__ = "password_reset_requests"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, approved, rejected
    created_at = db.Column(db.String(30), nullable=True)

    user = db.relationship("User", backref="password_reset_requests")

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "userId": str(self.user_id),
            "userName": self.user.name if self.user else "",
            "status": self.status,
            "createdAt": self.created_at,
        }


class RegistrationRequest(db.Model):
    """Žádosti o registraci – pouze e-mail, čeká na schválení adminem."""
    __tablename__ = "registration_requests"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), default="")
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, approved, rejected
    token = db.Column(db.String(64), nullable=True)  # pro odkaz na nastavení hesla
    token_expires = db.Column(db.String(30), nullable=True)  # ISO datetime
    approved_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.String(30), nullable=True)

    approved_user = db.relationship("User", backref="registration_request")

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "status": self.status,
            "createdAt": self.created_at,
            "approvedUserId": str(self.approved_user_id) if self.approved_user_id else None,
        }


class EmployeeRequest(db.Model):
    """Žádosti zaměstnanců: volno, zpoždění, výměna směny, záskok, přihláška na záskok."""
    __tablename__ = "employee_requests"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    type_ = db.Column(db.String(20), nullable=False)  # leave, late, swap, cover, cover_apply
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending, approved, rejected
    date_from = db.Column(db.String(10), nullable=True)  # pro volno
    date_to = db.Column(db.String(10), nullable=True)  # pro volno
    shift_date = db.Column(db.String(10), nullable=True)  # pro zpoždění – směna
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)  # propojení na směnu
    other_shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id"), nullable=True)  # pro swap – druhá směna
    applies_to_request_id = db.Column(db.Integer, nullable=True)  # pro cover_apply – žádost o záskok, na kterou se přihlašuji
    planned_time = db.Column(db.String(5), nullable=True)  # plánovaný čas
    actual_time = db.Column(db.String(5), nullable=True)  # skutečný příchod
    minutes_late = db.Column(db.Integer, nullable=True)  # počet minut zpoždění
    note = db.Column(db.String(512))

    employee = db.relationship("Employee", backref="requests")
    shift = db.relationship("Shift", foreign_keys=[shift_id])
    other_shift = db.relationship("Shift", foreign_keys=[other_shift_id])

    def to_dict(self):
        emp_dict = self.employee.to_dict() if self.employee else {"id": str(self.employee_id), "name": "", "email": "", "branch": None}
        d = {
            "id": str(self.id),
            "employeeId": str(self.employee_id),
            "employee": emp_dict,
            "type": self.type_,
            "status": self.status,
            "dateFrom": self.date_from,
            "dateTo": self.date_to,
            "shiftDate": self.shift_date,
            "shiftId": str(self.shift_id) if self.shift_id else None,
            "plannedTime": self.planned_time,
            "actualTime": self.actual_time,
            "minutesLate": self.minutes_late,
            "note": self.note,
        }
        d["otherShiftId"] = str(self.other_shift_id) if self.other_shift_id else None
        d["appliesToRequestId"] = str(self.applies_to_request_id) if self.applies_to_request_id else None
        if self.shift:
            emp_name = self.shift.employee.name if self.shift.employee else ""
            d["shift"] = {"id": str(self.shift.id), "date": self.shift.date, "startTime": self.shift.start_time, "endTime": self.shift.end_time, "employeeName": emp_name}
        if self.other_shift:
            emp_name = self.other_shift.employee.name if self.other_shift.employee else ""
            d["otherShift"] = {"id": str(self.other_shift.id), "date": self.other_shift.date, "startTime": self.other_shift.start_time, "endTime": self.other_shift.end_time, "employeeName": emp_name}
        return d


class Shift(db.Model):
    __tablename__ = "shifts"
    __table_args__ = (
        Index("ix_shifts_branch_date", "branch_id", "date"),
        Index("ix_shifts_employee_date", "employee_id", "date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)  # pobočka, kde směna proběhla; null = employee.branch_id
    date = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(5), default="08:00")
    end_time = db.Column(db.String(5), default="14:00")
    preset_id = db.Column(db.Integer, db.ForeignKey("shift_presets.id"))
    note = db.Column(db.String(512))

    preset = db.relationship("ShiftPreset")
    branch = db.relationship("Branch")

    def to_dict(self):
        preset_data = None
        if self.preset:
            preset_data = {"id": str(self.preset.id), "name": self.preset.name, "startTime": self.preset.start_time, "endTime": self.preset.end_time}
        bid = self.branch_id if self.branch_id else (self.employee.branch_id if self.employee else None)
        employee_data = self.employee.to_dict() if self.employee else None
        return {
            "id": str(self.id),
            "date": self.date,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "note": self.note,
            "branchId": str(bid) if bid else None,
            "employee": employee_data,
            "preset": preset_data,
        }


def _migrate_add_hourly_rates():
    for col, tbl in [("default_hourly_rate", "branches"), ("hourly_rate", "employees")]:
        try:
            db.session.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} REAL"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_swap_request_field():
    try:
        db.session.execute(text("ALTER TABLE employee_requests ADD COLUMN other_shift_id INTEGER REFERENCES shifts(id)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_cover_apply_field():
    try:
        db.session.execute(text("ALTER TABLE employee_requests ADD COLUMN applies_to_request_id INTEGER"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_late_request_fields():
    for col, tbl in [("minutes_late", "employee_requests"), ("shift_id", "employee_requests")]:
        try:
            db.session.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} INTEGER"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_add_user_role():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'admin'"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN employee_id INTEGER REFERENCES employees(id)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_add_manages_user():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN manages_user_id INTEGER REFERENCES users(id)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_shift_branch_id():
    try:
        db.session.execute(text("ALTER TABLE shifts ADD COLUMN branch_id INTEGER REFERENCES branches(id)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_employee_color():
    try:
        db.session.execute(text("ALTER TABLE employees ADD COLUMN color VARCHAR(7)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_user_ical_token():
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN ical_token VARCHAR(64)"))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _migrate_branch_weekend_hours():
    for col in ["open_time_weekend", "close_time_weekend"]:
        try:
            db.session.execute(text(f"ALTER TABLE branches ADD COLUMN {col} VARCHAR(5)"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_branch_opening_hours():
    for col, default in [("open_time", "08:00"), ("close_time", "20:00")]:
        try:
            db.session.execute(text(f"ALTER TABLE branches ADD COLUMN {col} VARCHAR(5)"))
            db.session.commit()
            db.session.execute(text(f"UPDATE branches SET {col} = '{default}' WHERE {col} IS NULL"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_add_indexes():
    """Přidá indexy pro výkon dotazů (shifts, employees)."""
    indexes = [
        ("ix_shifts_branch_date", "shifts", ["branch_id", "date"]),
        ("ix_shifts_employee_date", "shifts", ["employee_id", "date"]),
        ("ix_employees_branch_id", "employees", ["branch_id"]),
    ]
    for name, table, cols in indexes:
        try:
            db.session.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({', '.join(cols)})"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def init_db():
    db.create_all()
    _migrate_add_hourly_rates()
    _migrate_add_user_role()
    _migrate_late_request_fields()
    _migrate_add_manages_user()
    _migrate_shift_branch_id()
    _migrate_employee_color()
    _migrate_swap_request_field()
    _migrate_cover_apply_field()
    _migrate_user_ical_token()
    _migrate_branch_opening_hours()
    _migrate_branch_weekend_hours()
    _migrate_add_indexes()
    # Demo účet (demo@demo.cz / demo)
    if not User.query.filter_by(email="demo@demo.cz").first():
        from werkzeug.security import generate_password_hash
        u = User(email="demo@demo.cz", name="Demo", password_hash=generate_password_hash("demo"))
        db.session.add(u)
        db.session.flush()
        b = Branch(user_id=u.id, name="Moje směny")
        db.session.add(b)
        db.session.flush()
        e = Employee(branch_id=b.id, name="Já", email="demo@demo.cz")
        db.session.add(e)
        db.session.flush()
        for name, st, et in [("Ranní", "06:00", "14:00"), ("Odpolední", "14:00", "22:00")]:
            p = ShiftPreset(branch_id=b.id, name=name, start_time=st, end_time=et, pinned=True)
            db.session.add(p)
        db.session.commit()
