"""Testy API /api/login centrálního auth systému."""
import pytest
from app import app
from models import db, User, LoginLog


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def app_ctx():
    with app.app_context():
        yield


class TestApiLogin:
    """POST /api/login – ověření username + PIN."""

    def test_login_success_returns_username_role_branch(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "admin", "pin": "1234"},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert "branch" in data

    def test_login_success_with_application_logs_it(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "admin", "pin": "1234", "application": "odberos"},
            content_type="application/json",
        )
        assert r.status_code == 200
        with app.app_context():
            log = LoginLog.query.order_by(LoginLog.id.desc()).first()
            assert log is not None
            assert log.username == "admin"
            assert log.application == "odberos"

    def test_login_objednavac_returns_objednavac_role_when_set(self, client, app_ctx):
        with app.app_context():
            u = User(
                username="branch_user",
                role="user",
                branch="Praha",
                objednavac_role="branch",
                warehouse="",
                active=True,
            )
            u.set_pin("5678")
            db.session.add(u)
            db.session.commit()
        r = client.post(
            "/api/login",
            json={"username": "branch_user", "pin": "5678", "application": "objednavac"},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["role"] == "branch"
        assert data["branch"] == "Praha"

    def test_login_wrong_pin_401(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "admin", "pin": "9999"},
            content_type="application/json",
        )
        assert r.status_code == 401
        assert r.get_json()["ok"] is False
        assert "error" in r.get_json()

    def test_login_empty_username_401(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "", "pin": "1234"},
            content_type="application/json",
        )
        assert r.status_code == 401
        assert "jméno" in r.get_json().get("error", "").lower() or "username" in r.get_json().get("error", "").lower()

    def test_login_invalid_pin_too_short_401(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "admin", "pin": "12"},
            content_type="application/json",
        )
        assert r.status_code == 401
        assert "PIN" in r.get_json().get("error", "")

    def test_login_invalid_pin_letters_401(self, client, app_ctx):
        r = client.post(
            "/api/login",
            json={"username": "admin", "pin": "12ab"},
            content_type="application/json",
        )
        assert r.status_code == 401

    def test_login_inactive_user_401(self, client, app_ctx):
        with app.app_context():
            u = User(username="inactive", role="user", active=False)
            u.set_pin("5555")
            db.session.add(u)
            db.session.commit()
        r = client.post(
            "/api/login",
            json={"username": "inactive", "pin": "5555"},
            content_type="application/json",
        )
        assert r.status_code == 401
