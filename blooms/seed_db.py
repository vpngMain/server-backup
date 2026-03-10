#!/usr/bin/env python3
"""
Naplní databázi výchozími daty pro vývoj/test.
Použití: python seed_db.py
Předtím je vhodné spustit resetdb.py (nebo mít DB s vytvořenými tabulkami).
Vytvoří: uživatel admin / admin, volitelně 1 zákazník, 1 produkt.
Idempotentní – pokud admin už existuje, jen doplní chybějící (zákazník, produkt).
"""
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import DATABASE_URL
from app.db import Base, SessionLocal, create_engine
from app.models import (
    User, Customer, Product, DeliveryNote, DeliveryNoteItem,
    ImportBatch, ImportFile, ImportRow, AuditLog,
)
from app.models.user import UserRole
from app.auth.password import hash_password


def main():
    connect_args = {}
    if "sqlite" in DATABASE_URL:
        connect_args["check_same_thread"] = False
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

    # Tabulky vytvoř jen pokud neexistují (např. po resetdb už jsou)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Admin
        if db.query(User).filter(User.username == "admin").first() is None:
            db.add(User(
                username="admin",
                password_hash=hash_password("admin"),
                role=UserRole.admin.value,
                is_active=True,
            ))
            db.commit()
            print("Vytvořen uživatel: admin / admin")
        else:
            print("Uživatel admin již existuje.")

        # Jeden zákazník
        if db.query(Customer).count() == 0:
            db.add(Customer(company_name="Test Odběratel s.r.o.", ico="87654321"))
            db.commit()
            print("Vytvořen zákazník: Test Odběratel s.r.o.")
        else:
            print("Zákazníci již existují.")

        # Jeden produkt
        if db.query(Product).count() == 0:
            db.add(Product(
                description="Testovací rostlina",
                product_key_normalized="testovaci_rostlina_12",
                pot_size="12",
                active=True,
                sales_price_imported=Decimal("100.00"),
            ))
            db.commit()
            print("Vytvořen produkt: Testovací rostlina (12).")
        else:
            print("Produkty již existují.")

        # Prázdná dávka importu (kvůli některým testům)
        if db.query(ImportBatch).count() == 0:
            db.add(ImportBatch(
                source_folder="(seed)",
                total_files=0,
                total_rows=0,
                status="completed",
            ))
            db.commit()
            print("Vytvořena prázdná dávka importu.")

        print("")
        print("Seed hotov. Přihlášení: admin / admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
