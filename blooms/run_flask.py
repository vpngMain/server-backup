"""Spusteni Blooms jako Flask aplikace (prihlaseni pres Flask-Login)."""
import os
import sys

# Aby se v CMD/PowerShell neco vypsalo
print("Blooms Flask - startuji...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

from app.flask_app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", "5000"))
    # 0.0.0.0 = naslouchat na všech rozhraních (aby šlo na serveru přistupovat zvenku)
    # Na produkci dejte za reverse proxy (nginx) a FLASK_HOST=127.0.0.1 pro jen localhost
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    print("Server bezi na http://{}:{} - otevete v prohlizeci".format(host, port), flush=True)
    print("Ukonceni: Ctrl+C", flush=True)
    app.run(host=host, port=port, debug=True, use_reloader=False)
