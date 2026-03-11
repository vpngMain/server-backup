#!/usr/bin/env python3
"""
Import XLS/XLSX/CSV/TSV do databáze skladové aplikace (data/warehouse.db, tabulka products).
Řádky se stejným názvem nebo SKU aktualizuje, nové přidá.

Použití:
    python scripts/import_xls.py <soubor.xls|xlsx|csv|tsv> [cesta_k_db]

Výchozí databáze: data/warehouse.db

Příklad:
    python scripts/import_xls.py data.xls
    python scripts/import_xls.py data.csv
    python scripts/import_xls.py data.xlsx data/warehouse.db
"""

import os
import sys
import sqlite3

# Cesta ke kořeni projektu (nad scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def _get_engine(path):
    """Podle přípony vrátí engine pro pandas read_excel, nebo None pro CSV/TSV."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        return "xlrd"
    if ext in (".xlsx", ".xlsm"):
        return "openpyxl"
    return None


def _is_csv_or_tsv(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in (".csv", ".tsv")


def _normalize_columns(df):
    """Převod sloupců: nazev_skupiny, nazev, ks (jednotka: ks/ml/balení), volitelně sku (kód), pc."""
    col_map = {}
    for c in df.columns:
        cnorm = str(c).strip().lower().replace(" ", "_").replace("-", "_")
        if "skupin" in cnorm or cnorm == "group_name":
            col_map[c] = "nazev_skupiny"
        elif "nazev" in cnorm and "skupin" not in cnorm or cnorm == "name":
            col_map[c] = "nazev"
        elif cnorm == "ks":
            col_map[c] = "ks"   # jednotka (ks, ml, balení...)
        elif cnorm in ("sku", "code", "kod"):
            col_map[c] = "sku"  # kód produktu (volitelný)
        elif cnorm == "pc":
            col_map[c] = "pc"
    df = df.rename(columns=col_map)
    needed = ["nazev_skupiny", "nazev", "ks", "pc"]
    if "nazev" not in df.columns and len(df.columns) >= 4:
        df = df.iloc[:, :4].copy()
        df.columns = needed
    for n in needed + ["sku"]:
        if n not in df.columns:
            df[n] = ""
    return df[needed + ["sku"]].fillna("")


def _load_file(path, pd):
    """Načte soubor (Excel nebo CSV/TSV) a vrátí DataFrame se sloupci nazev_skupiny, nazev, ks, pc."""
    ext = os.path.splitext(path)[1].lower()
    if _is_csv_or_tsv(path):
        # CSV/TSV: detekce oddělovače z první řádky
        with open(path, "r", encoding="utf-8-sig") as f:
            first = f.readline()
        sep = "\t" if (ext == ".tsv" or ("\t" in first and "nazev" in first.lower())) else ","
        df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig", header=0)
    else:
        engine = _get_engine(path)
        if not engine:
            raise ValueError("Nepodporovaný formát. Použijte .xls, .xlsx, .csv nebo .tsv")
        df = pd.read_excel(path, engine=engine, dtype=str, header=0)
    return _normalize_columns(df)


def main():
    try:
        import pandas as pd
    except ImportError:
        print("Chybí závislost: nainstalujte pandas (pip install pandas).")
        sys.exit(1)

    INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else None
    DB_FILE = sys.argv[2] if len(sys.argv) > 2 else None

    if not INPUT_FILE or not os.path.isfile(INPUT_FILE):
        print("Použití: python scripts/import_xls.py <soubor.xls|xlsx|csv|tsv> [data/warehouse.db]")
        print("Soubor nebyl zadán nebo neexistuje.")
        sys.exit(1)

    if DB_FILE is None:
        DB_FILE = os.path.join(PROJECT_ROOT, "data", "warehouse.db")
    elif not os.path.isabs(DB_FILE):
        DB_FILE = os.path.join(PROJECT_ROOT, DB_FILE)

    if not _get_engine(INPUT_FILE) and not _is_csv_or_tsv(INPUT_FILE):
        print("Nepodporovaný formát. Použijte .xls, .xlsx, .csv nebo .tsv")
        sys.exit(1)

    print(f"Čtu soubor: {INPUT_FILE}")
    try:
        df = _load_file(INPUT_FILE, pd)
    except Exception as e:
        print(f"Chyba při čtení souboru: {e}")
        sys.exit(1)

    def norm(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, float) and val == int(val):
            val = int(val)
        s = str(val).strip()
        return s if s else None

    print(f"Načteno {len(df)} řádků.")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Tabulka products už existuje z Flask aplikace; vytvoříme ji jen při nové DB
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT,
            unit TEXT,
            group_name TEXT,
            pc TEXT
        )
    """)
    conn.commit()

    inserted = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        group_name = norm(row["nazev_skupiny"])
        name = norm(row["nazev"])
        unit = norm(row["ks"])      # jednotka: ks, ml, balení...
        sku = norm(row.get("sku")) # volitelný kód produktu
        pc = norm(row["pc"])

        if not name:
            skipped += 1
            continue

        # Stejný produkt = shodné SKU (pokud je), jinak (název + skupina + jednotka + pc)
        existing = None
        if sku:
            cur.execute("SELECT id FROM products WHERE sku = ?", (sku,))
            existing = cur.fetchone()
        if not existing:
            cur.execute(
                """SELECT id FROM products WHERE name = ?
                AND COALESCE(group_name, '') = COALESCE(?, '')
                AND COALESCE(unit, '') = COALESCE(?, '')
                AND COALESCE(pc, '') = COALESCE(?, '')""",
                (name, group_name, unit, pc),
            )
            existing = cur.fetchone()

        if existing:
            cur.execute(
                "UPDATE products SET name = ?, sku = ?, unit = ?, group_name = ?, pc = ? WHERE id = ?",
                (name, sku or None, unit or None, group_name or None, pc or None, existing[0]),
            )
            updated += 1
        else:
            cur.execute(
                "INSERT INTO products (name, sku, unit, group_name, pc) VALUES (?, ?, ?, ?, ?)",
                (name, sku or None, unit or None, group_name or None, pc or None),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"Hotovo. Přidáno: {inserted} | Aktualizováno: {updated} | Přeskočeno: {skipped}")


if __name__ == "__main__":
    main()
