#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Skript pro reset PPL databází – smaže ppl_warehouse.db a ppl_history.db.
POUŽÍVEJTE OPATRNĚ – SMAŽE VŠECHNA DATA PPL SKLADU BEZ OBNOVY!

Spustit: python reset_dbPPL.py
"""

import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir and os.path.exists(_script_dir):
    os.chdir(_script_dir)

from app import PPL_DATABASE, PPL_HISTORY_DB


def reset_ppl_db():
    """Smaže soubory PPL databází (warehouse + history). Při dalším běhu app je znovu vytvoří."""
    print("=" * 60)
    print("⚠️  VAROVÁNÍ: Tento skript smaže PPL databáze!")
    print("    - ppl_warehouse.db (zásilky, police, inventura)")
    print("    - ppl_history.db (historie akcí)")
    print("=" * 60)

    response = input("Opravdu chcete pokračovat? (ano/ne): ")
    if response.lower() != "ano":
        print("Operace zrušena.")
        return

    ok = True
    for path, label in [
        (PPL_DATABASE, "ppl_warehouse.db"),
        (PPL_HISTORY_DB, "ppl_history.db"),
    ]:
        if os.path.isfile(path):
            try:
                os.remove(path)
                print(f"✅ Smazáno: {label}")
            except OSError as e:
                print(f"❌ Chyba při mazání {label}: {e}")
                ok = False
        else:
            print(f"ℹ️  Soubor nenalezen (už smazán?): {label}")

    if ok:
        print("\n✅ PPL databáze byly resetovány. Při příštím spuštění aplikace se vytvoří znovu.")
    else:
        print("\n⚠️  Některé soubory se nepodařilo smazat (zkontrolujte oprávnění).")


if __name__ == "__main__":
    reset_ppl_db()
