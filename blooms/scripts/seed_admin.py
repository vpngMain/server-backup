"""Vytvoření výchozího admin uživatele. Spustit po migracích."""
import sys
from pathlib import Path

# Kořen projektu
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, Base, engine
from app.models import User
from app.auth.password import hash_password
from app.models.user import UserRole

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"  # Uživatel by měl po prvním přihlášení změnit


def main():
    # Zajistit, že tabulky existují
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == DEFAULT_USERNAME).first()
        if existing:
            print(f"Uživatel '{DEFAULT_USERNAME}' již existuje. Pro změnu hesla upravte ho v aplikaci (Uživatelé).")
            return
        user = User(
            username=DEFAULT_USERNAME,
            password_hash=hash_password(DEFAULT_PASSWORD),
            role=UserRole.admin.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Vytvořen admin uživatel: {DEFAULT_USERNAME} / {DEFAULT_PASSWORD}")
        print("PO PRVNÍM PŘIHLÁŠENÍ ZMIĚŇTE HESLO v sekci Uživatelé.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
