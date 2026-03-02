#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Skript pro smazání databáze – smaže všechny tabulky a u SQLite i soubor.
POUŽÍVEJTE OPATRNĚ – SMAŽE VŠECHNA DATA BEZ OBNOVY!

Spustit: python delete_db.py
"""

import os
import sys

# Nastavení pracovního adresáře na složku skriptu (kde je app.py)
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir and os.path.exists(_script_dir):
    os.chdir(_script_dir)

from app import app, db


def delete_database():
    """Smaže všechny tabulky a u SQLite i databázový soubor."""
    print("=" * 60)
    print("⚠️  VAROVÁNÍ: Tento skript smaže celou databázi!")
    print("    (všechny tabulky, u SQLite i soubor odbery.db)")
    print("=" * 60)

    response = input("Opravdu chcete pokračovat? (ano/ne): ")
    if response.lower() != "ano":
        print("Operace zrušena.")
        return

    with app.app_context():
        try:
            print("\n🗑️  Mažu všechny tabulky...")
            db.drop_all()
            db.session.commit()
            print("✅ Všechny tabulky byly smazány.")

            # U SQLite uvolníme připojení a případně smažeme soubor
            db_path = None
            uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
            if "sqlite" in uri.lower():
                # sqlite:///odbery.db -> odbery.db (relativně k CWD)
                db_path = uri.replace("sqlite:///", "").strip()
                if db_path and not os.path.isabs(db_path):
                    db_path = os.path.join(os.getcwd(), db_path)
            db.engine.dispose()

            if db_path and os.path.isfile(db_path):
                os.remove(db_path)
                print(f"✅ Soubor databáze byl smazán: {db_path}")
            elif db_path:
                print(f"ℹ️  Soubor databáze nebyl nalezen (už byl smazán?): {db_path}")

            print("\n✅ Databáze byla úspěšně smazána.")
            print("   Pro novou databázi spusťte: python reset_db.py")

        except Exception as e:
            print(f"\n❌ Chyba při mazání databáze: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except Exception:
                pass


if __name__ == "__main__":
    delete_database()
