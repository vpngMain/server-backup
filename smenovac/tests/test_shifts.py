"""Unit testy pro validaci směn (create/update)."""
import pytest
from app import app
from database import db, User, Branch, Employee, Shift, init_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Flask test client – používá DB z conftest (nastavenou před importem)."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with app.app_context():
            db.drop_all()
            db.create_all()
            admin = User(
                email="admin@test.cz",
                name="Admin",
                password_hash=generate_password_hash("admin123"),
                role="admin",
            )
            db.session.add(admin)
            db.session.flush()
            branch = Branch(user_id=admin.id, name="Pobočka A", open_time="08:00", close_time="20:00")
            db.session.add(branch)
            db.session.flush()
            emp = Employee(branch_id=branch.id, name="Jan", email="jan@test.cz")
            db.session.add(emp)
            db.session.flush()
            branch2 = Branch(user_id=admin.id, name="Pobočka B", open_time="08:00", close_time="20:00")
            db.session.add(branch2)
            db.session.flush()
            emp2 = Employee(branch_id=branch2.id, name="Marie", email="marie@test.cz")
            db.session.add(emp2)
            db.session.commit()
            yield c
            db.session.remove()
            db.drop_all()


def _login(client):
    """Přihlásí admina."""
    client.post(
        "/login",
        data={"email": "admin@test.cz", "password": "admin123"},
        follow_redirects=True,
    )


def test_invalid_time_range(client):
    """end_time <= start_time vrátí 400 s kódem INVALID_TIME_RANGE."""
    _login(client)
    r = client.post(
        "/api/shifts",
        json={
            "employeeId": 1,
            "branchId": 1,
            "date": "2026-02-25",
            "startTime": "14:00",
            "endTime": "10:00",
        },
        content_type="application/json",
    )
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_TIME_RANGE"
    assert "message" in data["error"]
    assert "details" in data["error"]


def test_shift_overlap(client):
    """Překryv směn pro stejného zaměstnance vrátí 409 s kódem SHIFT_OVERLAP."""
    _login(client)
    client.post(
        "/api/shifts",
        json={
            "employeeId": 1,
            "branchId": 1,
            "date": "2026-02-25",
            "startTime": "08:00",
            "endTime": "14:00",
        },
        content_type="application/json",
    )
    r = client.post(
        "/api/shifts",
        json={
            "employeeId": 1,
            "branchId": 1,
            "date": "2026-02-25",
            "startTime": "12:00",
            "endTime": "18:00",
        },
        content_type="application/json",
    )
    assert r.status_code == 409
    data = r.get_json()
    assert "error" in data
    assert data["error"]["code"] == "SHIFT_OVERLAP"
    assert "message" in data["error"]
    assert "existingShift" in data["error"].get("details", {})


def test_employee_branch_mismatch(client):
    """Zaměstnanec z jiné pobočky vrátí 400 s kódem EMPLOYEE_BRANCH_MISMATCH."""
    _login(client)
    r = client.post(
        "/api/shifts",
        json={
            "employeeId": 1,
            "branchId": 2,
            "date": "2026-02-25",
            "startTime": "08:00",
            "endTime": "14:00",
        },
        content_type="application/json",
    )
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data
    assert data["error"]["code"] == "EMPLOYEE_BRANCH_MISMATCH"
    assert "message" in data["error"]


def test_valid_shift_created(client):
    """Korektní směna se vytvoří a vrátí 201."""
    _login(client)
    r = client.post(
        "/api/shifts",
        json={
            "employeeId": 1,
            "branchId": 1,
            "date": "2026-02-25",
            "startTime": "08:00",
            "endTime": "14:00",
        },
        content_type="application/json",
    )
    assert r.status_code == 201
    data = r.get_json()
    assert data["date"] == "2026-02-25"
    assert data["startTime"] == "08:00"
    assert data["endTime"] == "14:00"
