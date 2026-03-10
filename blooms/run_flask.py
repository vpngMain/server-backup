"""Spusteni Blooms jako Flask aplikace (prihlaseni pres Flask-Login)."""
import sys

# Aby se v CMD/PowerShell neco vypsalo
print("Blooms Flask - startuji...", flush=True)
sys.stdout.flush()
sys.stderr.flush()

from app.flask_app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("FLASK_PORT", "5000"))
    print("Server bezi na http://127.0.0.1:{} - otevete v prohlizeci".format(port), flush=True)
    print("Ukonceni: Ctrl+C", flush=True)
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
