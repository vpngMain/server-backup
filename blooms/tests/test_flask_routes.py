"""Integrační testy Flask rout – přihlášení, seznam produktů, vytvoření dodacího listu."""
import pytest


class TestLogin:
    def test_login_page_returns_200(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_login_with_valid_credentials_redirects_to_dashboard(self, client):
        r = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert r.status_code == 302
        assert "/dashboard" in (r.location or "")

    def test_login_with_invalid_credentials_redirects_back(self, client):
        r = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
        assert r.status_code == 302
        assert "login" in (r.location or "")

    def test_dashboard_requires_login(self, client):
        r = client.get("/dashboard", follow_redirects=False)
        assert r.status_code in (302, 401)
        if r.status_code == 302:
            assert "login" in (r.location or "")


class TestProductsList:
    def test_products_require_login(self, client):
        r = client.get("/products", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in (r.location or "")

    def test_products_list_200_when_logged_in(self, logged_in_client):
        r = logged_in_client.get("/products")
        assert r.status_code == 200
        assert b"Produkty" in r.data or b"produkt" in r.data.lower()


class TestDeliveryNote:
    def test_delivery_list_requires_login(self, client):
        r = client.get("/delivery", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in (r.location or "")

    def test_delivery_new_200_when_logged_in(self, logged_in_client):
        r = logged_in_client.get("/delivery/new")
        assert r.status_code == 200

    def test_delivery_create_creates_note(self, logged_in_client, app):
        from app.db import SessionLocal
        from app.models import Customer, DeliveryNote

        with app.app_context():
            db = SessionLocal()
            try:
                customer = db.query(Customer).first()
                if not customer:
                    customer = Customer(
                        company_name="Test s.r.o.",
                        ico="12345678",
                    )
                    db.add(customer)
                    db.commit()
                customer_id = customer.id
            finally:
                db.close()

        r = logged_in_client.post(
            "/delivery/new",
            data={
                "document_number": "DL-2025-0001",
                "customer_id": str(customer_id),
                "issue_date": "2025-03-09",
                "delivery_date": "2025-03-10",
                "note": "",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/delivery/" in (r.location or "")
        assert "new" not in (r.location or "")
