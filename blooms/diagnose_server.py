#!/usr/bin/env python3
"""Diagnostika Blooms na serveru – spusťte na serveru: python diagnose_server.py"""
import os
import sys

def main():
    print("=== Blooms – diagnostika serveru ===\n", flush=True)
    errors = []

    # 1. Cesta a pracovní adresář
    try:
        from pathlib import Path
        from app.config import BASE_DIR
        cwd = Path.cwd()
        print("Pracovní adresář:", cwd)
        print("BASE_DIR (app):", BASE_DIR)
        print("BASE_DIR existuje:", BASE_DIR.exists())
        if not BASE_DIR.exists():
            errors.append("BASE_DIR neexistuje – jste ve správné složce projektu?")
    except Exception as e:
        errors.append("Import config: " + str(e))
        print("CHYBA config:", e)
        return 1

    # 2. Šablony a static
    try:
        templates = BASE_DIR / "app" / "templates"
        static = BASE_DIR / "app" / "static"
        print("\nSložka templates existuje:", templates.exists())
        print("Složka static existuje:", static.exists())
        if not templates.exists():
            errors.append("Chybí app/templates")
    except Exception as e:
        errors.append("Kontrola složek: " + str(e))

    # 3. Databáze
    try:
        from app.config import DATABASE_URL
        print("\nDATABASE_URL:", DATABASE_URL.split("///")[-1] if "///" in DATABASE_URL else "(skryto)")
        from app.db import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("Databáze: OK")
    except Exception as e:
        errors.append("Databáze: " + str(e))
        print("Databáze CHYBA:", e)

    # 4. Flask app
    try:
        from app.flask_app import create_app
        app = create_app()
        with app.app_context():
            print("\nFlask app: OK")
            print("Registrované blueprints:", list(app.blueprints.keys()))
    except Exception as e:
        errors.append("Flask app: " + str(e))
        print("Flask app CHYBA:", e)
        import traceback
        traceback.print_exc()

    # 5. Port a host
    port = int(os.environ.get("FLASK_PORT", "5000"))
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    print("\nFLASK_PORT:", port)
    print("FLASK_HOST:", host, "(0.0.0.0 = přístup zvenku, 127.0.0.1 = jen localhost)")

    # Shrnutí
    print("\n" + "="*50)
    if errors:
        print("CHYBY:")
        for e in errors:
            print("  -", e)
        print("\nOpravte chyby a pak spusťte: python run_flask.py")
        return 1
    else:
        print("Základní diagnostika prošla. Spusťte: python run_flask.py")
        print("Pak v prohlížeči: http://<IP-serveru>:{}".format(port))
        return 0

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
