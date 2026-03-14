"""Pytest konfigurace a fixtures pro testování Vaping směnovač."""
import os
import tempfile
import pytest

# DB URI PŘED importem app – Flask-SQLAlchemy načítá config jen při init_app()
_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import app
from database import db, User, Branch, Employee, Shift, init_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Flask test client s testovací SQLite databází."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        with app.app_context():
            db.create_all()
            _create_test_data(db.session)
            yield c
            db.session.remove()
            db.drop_all()


def _create_test_data(db_session):
    """Vytvoří testovací admina, pobočku a zaměstnance."""
    admin = User(
        email="admin@test.cz",
        name="Admin",
        password_hash=generate_password_hash("admin123"),
        role="admin",
    )
    db_session.add(admin)
    db_session.flush()

    branch = Branch(user_id=admin.id, name="Pobočka A", open_time="08:00", close_time="20:00")
    db_session.add(branch)
    db_session.flush()

    emp = Employee(branch_id=branch.id, name="Jan Novák", email="jan@test.cz")
    db_session.add(emp)
    db_session.flush()

    branch2 = Branch(user_id=admin.id, name="Pobočka B", open_time="08:00", close_time="20:00")
    db_session.add(branch2)
    db_session.flush()

    emp2 = Employee(branch_id=branch2.id, name="Marie Nová", email="marie@test.cz")
    db_session.add(emp2)

    db_session.commit()


@pytest.fixture
def auth_headers(client):
    """Přihlášení a vrácení session cookie pro autentizované requesty."""
    r = client.post(
        "/login",
        data={"email": "admin@test.cz", "password": "admin123"},
        follow_redirects=True,
    )
    assert r.status_code in (200, 302)
    return client

