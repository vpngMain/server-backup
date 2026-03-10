#!/usr/bin/env python3
"""
Reset databáze: smaže všechny tabulky a znovu je vytvoří dle aktuálních modelů.
Použití: python resetdb.py
Pro SQLite se soubor blooms.db přepíše (prázdná DB).
"""
import sys
from pathlib import Path

# Kořen projektu na path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import create_engine

from app.config import DATABASE_URL
from app.db import Base

# Načíst všechny modely, aby Base.metadata znal jejich tabulky
from app.models import (  # noqa: F401
    User,
    Product,
    ImportBatch,
    ImportFile,
    ImportRow,
    Customer,
    DeliveryNote,
    DeliveryNoteItem,
    AuditLog,
)


def main():
    connect_args = {}
    if "sqlite" in DATABASE_URL:
        connect_args["check_same_thread"] = False
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

    print("Mažu všechny tabulky...")
    Base.metadata.drop_all(bind=engine)

    print("Vytvářím tabulky z modelů...")
    Base.metadata.create_all(bind=engine)

    # Označit Alembic, že jsme na aktuálním schématu (volitelné)
    if "--stamp" in sys.argv:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(Path(__file__).parent / "alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
        command.stamp(alembic_cfg, "head")
        print("Alembic stamp head proveden.")

    print("Hotovo. Databáze je prázdná a má aktuální schéma.")
    print("Poznámka: Pro výchozí data (uživatel, produkty) spusť seed nebo testovací fixture.")


if __name__ == "__main__":
    main()
