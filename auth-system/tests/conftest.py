# TESTING musí být nastaveno před importem app (kvůli in-memory DB)
import os
import sys

os.environ["TESTING"] = "1"
# Kořen auth-system do path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import app
from models import db, User


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


@pytest.fixture
def app_ctx():
    with app.app_context():
        yield
