#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WSGI konfigurace pro PythonAnywhere
Tento soubor se používá pro nasazení aplikace na PythonAnywhere.
"""

import sys
import os

# Přidáme cestu k projektu do Python path (lokálně = adresář tohoto souboru)
path = os.environ.get('ODBEROS_SITE_PATH') or os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

# Nastavíme working directory
os.chdir(path)

# Importujeme aplikaci
from app import app as application

# Nastavíme proměnné prostředí (volitelné, pokud je chcete nastavit zde)
# os.environ['SECRET_KEY'] = 'your-secret-key-here'
# os.environ['DATABASE_URL'] = 'sqlite:///odbery.db'

if __name__ == "__main__":
    application.run()
