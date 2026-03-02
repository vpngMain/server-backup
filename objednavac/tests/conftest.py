"""
Pytest fixtures pro Selenium testy.
Spouští Flask aplikaci na náhodném portu a poskytuje Chrome/Chromium driver.
"""
import os
import sys
import tempfile
import threading
import time

import pytest

# Testovací DB musí být nastavena před importem app
_TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["TESTING"] = "1"
os.environ["TEST_DATABASE_URI"] = "sqlite:///" + _TEST_DB.replace("\\", "/")

# Kořen projektu do path (pro import app)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, _seed_admin  # noqa: E402


@pytest.fixture(scope="session")
def test_db():
    """Testovací DB soubor – vytvořen app při importu."""
    return _TEST_DB


@pytest.fixture(scope="session")
def live_server_url():
    """Spustí Flask server na volném portu a vrátí base URL."""
    from werkzeug.serving import make_server

    server_holder = []
    port_holder = []

    def run():
        srv = make_server("127.0.0.1", 0, app, threaded=True)
        server_holder.append(srv)
        port_holder.append(srv.server_port)
        srv.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    for _ in range(50):
        if server_holder:
            break
        time.sleep(0.1)
    assert server_holder, "Server se nespustil"
    server = server_holder[0]
    port = port_holder[0] if port_holder else server.server_port
    url = f"http://127.0.0.1:{port}"
    yield url
    server.shutdown()


@pytest.fixture(scope="function")
def chrome_driver():
    """Chrome/Chromium WebDriver (headless). Používá Selenium Manager – stáhne driver odpovídající verzi prohlížeče."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Na Linuxu často běží Chromium místo Chrome – nastav cestu, ať Selenium Manager stáhne správný driver
    for path in ("/usr/sbin/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if os.path.isfile(path):
            options.binary_location = path
            break
    # Bez Service: Selenium 4.6+ stáhne chromedriver odpovídající nainstalovanému prohlížeči
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(15)
    yield driver
    driver.quit()


@pytest.fixture(scope="function")
def browser(live_server_url, chrome_driver):
    """Selenium driver + base URL aplikace."""
    chrome_driver.base_url = live_server_url
    return chrome_driver


@pytest.fixture(scope="session", autouse=True)
def seed_admin_user():
    """Po vytvoření testovací DB vytvoří admina (admin/admin)."""
    with app.app_context():
        _seed_admin()
