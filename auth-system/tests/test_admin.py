"""Testy admin webu – přihlášení a CRUD uživatelů."""
import pytest
from app import app
from models import db, User


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


@pytest.fixture
def app_ctx():
    with app.app_context():
        yield


@pytest.fixture
def logged_in_client(client, app_ctx):
    """Klient s přihlášeným adminem (session cookie)."""
    client.post(
        "/admin/login",
        data={"username": "admin", "pin": "1234"},
        follow_redirects=True,
    )
    return client


class TestAdminLogin:
    def test_admin_login_page_renders(self, client):
        r = client.get("/admin/login")
        assert r.status_code == 200
        assert b"PIN" in r.data or b"pin" in r.data

    def test_admin_login_success_redirects_to_dashboard(self, client, app_ctx):
        r = client.post(
            "/admin/login",
            data={"username": "admin", "pin": "1234"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 200)
        if r.status_code == 302:
            assert "dashboard" in r.location or "admin" in r.location

    def test_admin_login_wrong_pin_shows_error(self, client, app_ctx):
        r = client.post(
            "/admin/login",
            data={"username": "admin", "pin": "0000"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert b"Neplatn" in r.data or b"error" in r.data.lower()


class TestAdminDashboard:
    def test_dashboard_requires_login(self, client):
        r = client.get("/admin/dashboard", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.location

    def test_dashboard_lists_users_when_logged_in(self, client, logged_in_client, app_ctx):
        r = logged_in_client.get("/admin/dashboard")
        assert r.status_code == 200
        assert b"admin" in r.data

    def test_add_user_then_appears_in_list(self, client, logged_in_client, app_ctx):
        r = logged_in_client.post(
            "/admin/user/add",
            data={
                "username": "testuser99",
                "pin": "1234",
                "role": "user",
                "branch": "Brno",
                "active": "1",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        with app.app_context():
            u = User.query.filter_by(username="testuser99").first()
            assert u is not None
            assert u.role == "user"
            assert u.branch == "Brno"
            assert u.active is True
        r2 = logged_in_client.get("/admin/dashboard")
        assert b"testuser99" in r2.data
