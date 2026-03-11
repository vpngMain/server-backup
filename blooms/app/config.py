"""Konfigurace aplikace."""
import os
from pathlib import Path

# Cesta k databázi - v kořeni projektu
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'blooms.db'}")

# Secret pro session
SECRET_KEY = os.getenv("SECRET_KEY", "blooms-internal-dev-change-in-production")

# Session
SESSION_COOKIE_NAME = "blooms_session"
SESSION_MAX_AGE = 86400 * 7  # 7 dní

# Bez přihlášení v dev: True = vždy první uživatel z DB (bez cookie). Vypni jen na produkci.
_dev = os.getenv("DEV_SKIP_AUTH", "").strip().lower()
DEV_SKIP_AUTH = _dev not in ("0", "false", "no")  # výchozí True; pro vypnutí: DEV_SKIP_AUTH=0

# UI experimenty / postupné migrace
_tab = os.getenv("USE_TABULATOR", "1").strip().lower()
USE_TABULATOR = _tab not in ("0", "false", "no")

# Firemní hlavička pro dodací list / PDF
COMPANY_NAME = os.getenv("COMPANY_NAME", "Moje firma s.r.o.").strip()
COMPANY_STREET = os.getenv("COMPANY_STREET", "").strip()
COMPANY_CITY = os.getenv("COMPANY_CITY", "").strip()
COMPANY_ZIP = os.getenv("COMPANY_ZIP", "").strip()
COMPANY_COUNTRY = os.getenv("COMPANY_COUNTRY", "Česká republika").strip()
COMPANY_ICO = os.getenv("COMPANY_ICO", "").strip()
COMPANY_DIC = os.getenv("COMPANY_DIC", "").strip()
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "").strip()
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "").strip()
