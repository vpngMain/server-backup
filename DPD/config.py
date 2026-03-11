import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(BASE_DIR, "instance", "db.sqlite"),
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB pro uploady

# PIN: 4-6 číslic
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6
