#!/usr/bin/env python3
"""Reset databáze na čisto: smaže všechny tabulky a znovu je vytvoří včetně demo účtu (demo@demo.cz / demo)."""
import os
import sys

# Načíst .env před importem app
try:
    from pathlib import Path
    from dotenv import load_dotenv
    p = Path(__file__).resolve().parent / ".env"
    load_dotenv(p)
except ImportError:
    pass

# Import až po načtení .env (kvůli DATABASE_URL)
from app import app
from database import db, init_db

def main():
    with app.app_context():
        db.drop_all()
        init_db()
    print("Databáze resetována. Tabulky znovu vytvořeny, demo účet: demo@demo.cz / demo")
    return 0

if __name__ == "__main__":
    sys.exit(main())
