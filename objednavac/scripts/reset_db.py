#!/usr/bin/env python3
"""
Skript pro reset databáze. Spusť z kořene projektu:

  python scripts/reset_db.py          # po resetu vytvoří admina (admin/admin)
  python scripts/reset_db.py --no-seed   # reset bez vytvoření admina

Nebo použij Flask CLI:

  flask reset-db
  flask reset-db --no-seed
"""
import sys
import os

# Kořen projektu = parent složky scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, _reset_db


def main():
    no_seed = "--no-seed" in sys.argv
    with app.app_context():
        _reset_db(seed_admin=not no_seed)
    print("Databáze byla resetována." + ("" if no_seed else " Admin vytvořen (admin/admin)."))


if __name__ == "__main__":
    main()
