"""Konfigurace centrálního auth systému."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "change-in-production-auth-system")
if os.environ.get("TESTING"):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
else:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "auth.db"),
    )
if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URI = "postgresql://" + SQLALCHEMY_DATABASE_URI[11:]
SQLALCHEMY_TRACK_MODIFICATIONS = False

# PIN: 4–6 číslic (dle app.md)
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 10

# Role pro Objednávač
OBJEDNAVAC_ROLES = ("admin", "branch", "warehouse")

# SSO: sdílené heslo pro vytváření tokenů ze Směrosu (Stejnou hodnotu nastavte ve Směrosu!)
# Bez nastavení se použije výchozí – SSO pak funguje bez konfigurace; v produkci nastavte silné heslo.
SSO_SECRET = (os.environ.get("SSO_SECRET") or "sso-dev-secret").strip()
SSO_TOKEN_TTL_SECONDS = 60
