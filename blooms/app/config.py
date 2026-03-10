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
