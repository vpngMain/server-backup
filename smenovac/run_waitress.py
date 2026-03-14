"""Spuštění na síti (Waitress). Pro Windows. python run_waitress.py"""
import os
import sys

print("Načítám aplikaci...", flush=True)
from app import app

import waitress
port = int(os.environ.get("PORT", 5000))
print(f"Spouštím server na http://0.0.0.0:{port} (Ctrl+C = ukončit)", flush=True)
sys.stdout.flush()
sys.stderr.flush()

# 0.0.0.0 = poslouchá na všech síťových rozhraních (dostupné v síti)
waitress.serve(app, host="0.0.0.0", port=port, url_scheme="http", threads=4)
