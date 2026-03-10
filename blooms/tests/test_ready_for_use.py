"""
Heavy testy – ověření, že aplikace je ready for use.

Spuštění z CMD:

  cd C:\\cesta\\k\\blooms
  python -m pytest tests/test_ready_for_use.py -v

Nebo z adresáře tests:

  cd C:\\cesta\\k\\blooms\\tests
  python -m pytest test_ready_for_use.py -v

Všechny testy:  python -m pytest tests/ -v
"""
from decimal import Decimal


class TestAuthFullFlow:
    """Přihlášení, odhlášení, ochrana stránek."""

    def test_login_get_200(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert b"login" in r.data.lower() or b"username" in r.data.lower()

    def test_login_post_success_redirects_dashboard(self, client):
        r = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert r.status_code == 302
        assert "dashboard" in (r.location or "")

    def test_login_post_invalid_redirects_login(self, client):
        r = client.post("/login", data={"username": "admin", "password": "wrong"}, follow_redirects=False)
        assert r.status_code == 302
        assert "login" in (r.location or "")

    def test_after_login_dashboard_200(self, logged_in_client):
        r = logged_in_client.get("/dashboard")
        assert r.status_code == 200
        assert b"Dashboard" in r.data or b"dashboard" in r.data

    def test_logout_redirects_login(self, logged_in_client):
        r = logged_in_client.get("/logout", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in (r.location or "")

    def test_protected_routes_redirect_when_not_logged_in(self, client):
        for path in ["/dashboard", "/products", "/customers", "/delivery", "/import", "/import/history"]:
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 302, f"GET {path} should redirect when not logged in"
            assert "login" in (r.location or ""), f"GET {path} should redirect to login"


class TestDashboard:
    """Dashboard – statistiky, odkazy."""

    def test_dashboard_200_with_seeded_data(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/dashboard")
        assert r.status_code == 200
        assert b"Produkty" in r.data or b"produkt" in r.data
        assert b"delivery" in r.data or b"Dodac" in r.data or b"dodac" in r.data
        assert b"Odb" in r.data or b"odberatel" in r.data or b"customer" in r.data

    def test_dashboard_has_statistics_section(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/dashboard")
        assert r.status_code == 200
        assert b"Statistiky" in r.data or b"statistik" in r.data


class TestProductsFullFlow:
    """Produkty – seznam, detail, vyhledávání, export, 404."""

    def test_products_list_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products")
        assert r.status_code == 200
        assert b"Produkty" in r.data
        assert b"Testovac" in r.data or b"rostlina" in r.data or b"Export" in r.data

    def test_products_detail_200(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import Product
        with app.app_context():
            db = SessionLocal()
            p = db.query(Product).first()
            pid = p.id if p else 1
            db.close()
        r = logged_in_seeded_client.get(f"/products/{pid}")
        assert r.status_code == 200
        assert b"Detail" in r.data or b"description" in r.data

    def test_products_detail_404_invalid_id(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products/999999")
        assert r.status_code == 404

    def test_products_search_fragment_returns_html(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products/search?q=test")
        assert r.status_code == 200
        assert b"list-group" in r.data or b"test" in r.data or b"znak" in r.data

    def test_products_export_csv_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products/export?format=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert b"Description" in r.data or b"description" in r.data or b"ID" in r.data

    def test_products_export_xlsx_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products/export?format=xlsx")
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("Content-Type", "") or "xlsx" in r.headers.get("Content-Type", "")


class TestCustomersFullFlow:
    """Odběratelé – seznam, nový, detail, editace, 404."""

    def test_customers_list_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/customers")
        assert r.status_code == 200
        assert b"Odb" in r.data or b"odberatel" in r.data or b"Test Odb" in r.data

    def test_customers_new_get_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/customers/new")
        assert r.status_code == 200

    def test_customers_detail_200(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import Customer
        with app.app_context():
            db = SessionLocal()
            c = db.query(Customer).first()
            cid = c.id if c else 1
            db.close()
        r = logged_in_seeded_client.get(f"/customers/{cid}")
        assert r.status_code == 200
        assert b"Test Odb" in r.data or b"company" in r.data

    def test_customers_detail_404(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/customers/999999")
        assert r.status_code == 404

    def test_customers_edit_get_200(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import Customer
        with app.app_context():
            db = SessionLocal()
            c = db.query(Customer).first()
            cid = c.id if c else 1
            db.close()
        r = logged_in_seeded_client.get(f"/customers/{cid}/edit")
        assert r.status_code == 200


class TestDeliveryFullFlow:
    """Dodací listy – seznam, nový, detail, položky, 404."""

    def test_delivery_list_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/delivery")
        assert r.status_code == 200
        assert b"Dodac" in r.data or b"dodaci" in r.data

    def test_delivery_new_get_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/delivery/new")
        assert r.status_code == 200
        assert b"document_number" in r.data or b"document" in r.data or b"DL-" in r.data

    def test_delivery_detail_200(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import DeliveryNote
        with app.app_context():
            db = SessionLocal()
            n = db.query(DeliveryNote).first()
            nid = n.id if n else 1
            db.close()
        r = logged_in_seeded_client.get(f"/delivery/{nid}")
        assert r.status_code == 200
        assert b"DL-" in r.data or b"poloz" in r.data or b"item" in r.data

    def test_delivery_detail_404(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/delivery/999999")
        assert r.status_code == 404

    def test_delivery_create_post_redirects_to_detail(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import Customer
        with app.app_context():
            db = SessionLocal()
            c = db.query(Customer).first()
            cid = c.id
            db.close()
        r = logged_in_seeded_client.post(
            "/delivery/new",
            data={
                "document_number": "DL-2025-0099",
                "customer_id": str(cid),
                "issue_date": "2025-03-15",
                "delivery_date": "2025-03-20",
                "note": "",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/delivery/" in (r.location or "") and "new" not in (r.location or "")


class TestImportPages:
    """Import – historie, detail batch."""

    def test_import_page_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/import")
        assert r.status_code == 200
        assert b"Import" in r.data or b"import" in r.data.lower()

    def test_import_history_200(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/import/history")
        assert r.status_code == 200
        assert b"Historie" in r.data or b"history" in r.data

    def test_import_batch_detail_200(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import ImportBatch
        with app.app_context():
            db = SessionLocal()
            b = db.query(ImportBatch).first()
            bid = b.id if b else 1
            db.close()
        r = logged_in_seeded_client.get(f"/import/history/{bid}")
        assert r.status_code == 200

    def test_import_batch_detail_404(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/import/history/999999")
        assert r.status_code == 404


class TestUsersAccess:
    """Uživatelé – pouze admin."""

    def test_users_list_200_as_admin(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/users")
        assert r.status_code == 200
        assert b"Uzivatel" in r.data or b"user" in r.data or b"admin" in r.data

    def test_users_new_get_200_as_admin(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/users/new")
        assert r.status_code == 200


class TestErrorPages:
    """Vlastní stránky chyb."""

    def test_404_page_renders(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/products/999999")
        assert r.status_code == 404
        assert b"404" in r.data
        assert b"dashboard" in r.data


class TestLoadersInvalidId:
    """Validace ID – neexistující záznam = 404."""

    def test_product_invalid_id_404(self, logged_in_seeded_client):
        assert logged_in_seeded_client.get("/products/0").status_code == 404
        assert logged_in_seeded_client.get("/products/99999").status_code == 404

    def test_customer_invalid_id_404(self, logged_in_seeded_client):
        assert logged_in_seeded_client.get("/customers/99999").status_code == 404

    def test_delivery_invalid_id_404(self, logged_in_seeded_client):
        assert logged_in_seeded_client.get("/delivery/99999").status_code == 404
        assert logged_in_seeded_client.get("/delivery/99999/print").status_code == 404


class TestAuditLogOnUpdate:
    """Audit log – zápis při úpravě produktu a dodacího listu."""

    def test_product_update_creates_audit_entry(self, logged_in_seeded_client, app):
        from app.db import SessionLocal
        from app.models import Product, AuditLog
        with app.app_context():
            db = SessionLocal()
            p = db.query(Product).first()
            pid = p.id
            count_before = db.query(AuditLog).filter(
                AuditLog.entity_type == "product",
                AuditLog.entity_id == pid,
            ).count()
            db.close()
        logged_in_seeded_client.post(
            f"/products/{pid}",
            data={
                "description": "Testovací rostlina",
                "description2": "",
                "pot_size": "12",
                "active": "1",
            },
            follow_redirects=True,
        )
        with app.app_context():
            db = SessionLocal()
            count_after = db.query(AuditLog).filter(
                AuditLog.entity_type == "product",
                AuditLog.entity_id == pid,
            ).count()
            db.close()
        assert count_after >= count_before + 1


class TestStatsService:
    """Statistiky – bez pádů při prázdné/naplněné DB."""

    def test_dashboard_stats_no_error(self, logged_in_seeded_client):
        r = logged_in_seeded_client.get("/dashboard")
        assert r.status_code == 200
        assert b"Statistiky" in r.data or b"statistik" in r.data

    def test_top_customers_top_products_no_crash(self, app):
        from app.db import SessionLocal
        from app.services.stats_service import top_customers_by_revenue, top_products_by_quantity, delivery_notes_by_month
        with app.app_context():
            db = SessionLocal()
            top_customers_by_revenue(db, limit=5)
            top_products_by_quantity(db, limit=5)
            delivery_notes_by_month(db, months=6)
            db.close()


class TestDeliveryNoteService:
    """Služby dodacích listů – číslování, přepočet."""

    def test_next_document_number(self, app):
        from app.db import SessionLocal
        from app.services.delivery_note_service import next_document_number
        with app.app_context():
            db = SessionLocal()
            num = next_document_number(db)
            db.close()
        assert num.startswith("DL-")
        assert "0001" in num or "0002" in num
