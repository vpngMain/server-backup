"""Pytest konfigurace a společné fixtures."""
import os
import sys
from pathlib import Path

import pytest

# Kořen projektu na path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Testovací DB a secret před importem app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEV_SKIP_AUTH", "0")


@pytest.fixture
def app():
    from app.flask_app import create_app
    from app.db import Base, engine, SessionLocal
    from app.models import User
    from app.auth.password import hash_password
    from app.models.user import UserRole

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # testy neposílají CSRF token
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == "admin").first()
        if not u:
            db.add(User(
                username="admin",
                password_hash=hash_password("admin"),
                role=UserRole.admin.value,
                is_active=True,
            ))
            db.commit()
    finally:
        db.close()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    """Klient přihlášený jako admin/admin."""
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    return client


@pytest.fixture
def seeded_db(app):
    """Naplní DB minimálními daty: admin, customer, product, delivery_note s položkou."""
    from app.db import SessionLocal
    from app.models import (
        User, Customer, Product, DeliveryNote, DeliveryNoteItem,
        ImportBatch, AuditLog,
    )
    from app.auth.password import hash_password
    from app.models.user import UserRole
    from datetime import date
    from decimal import Decimal

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == "admin").first() is None:
            db.add(User(
                username="admin",
                password_hash=hash_password("admin"),
                role=UserRole.admin.value,
                is_active=True,
            ))
            db.commit()
        if db.query(Customer).count() == 0:
            c = Customer(company_name="Test Odběratel s.r.o.", ico="87654321")
            db.add(c)
            db.commit()
        if db.query(Product).count() == 0:
            p = Product(
                description="Testovací rostlina",
                product_key_normalized="testovaci_rostlina_12",
                pot_size="12",
                active=True,
                sales_price_imported=Decimal("100.00"),
            )
            db.add(p)
            db.commit()
        if db.query(DeliveryNote).count() == 0:
            cust = db.query(Customer).first()
            prod = db.query(Product).first()
            note = DeliveryNote(
                document_number="DL-2025-0001",
                customer_id=cust.id,
                issue_date=date(2025, 3, 1),
                delivery_date=date(2025, 3, 10),
                status="draft",
            )
            db.add(note)
            db.flush()
            item = DeliveryNoteItem(
                delivery_note_id=note.id,
                product_id=prod.id,
                item_name=prod.description,
                quantity=Decimal("2"),
                unit="ks",
                unit_price=Decimal("100"),
                line_total=Decimal("200"),
                sort_order=0,
                is_manual_item=False,
            )
            db.add(item)
            note.total_amount = Decimal("200")
            db.commit()
        if db.query(ImportBatch).count() == 0:
            batch = ImportBatch(
                source_folder="C:\\Test",
                total_files=0,
                total_rows=0,
                status="completed",
            )
            db.add(batch)
            db.commit()
    finally:
        db.close()
    return app


@pytest.fixture
def seeded_client(seeded_db):
    """Test client s naplněnou DB (customer, product, delivery note, import batch)."""
    return seeded_db.test_client()


@pytest.fixture
def logged_in_seeded_client(seeded_client):
    """Přihlášený klient + naplněná DB."""
    seeded_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    return seeded_client
