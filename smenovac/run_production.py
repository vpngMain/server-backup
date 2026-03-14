"""Spuštění pro produkci (Gunicorn). Použití: gunicorn run_production:app"""
from app import app

# Gunicorn načte objekt app
