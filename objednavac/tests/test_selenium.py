"""
Selenium (Chrome/Chromium) testy – ověření, že webová aplikace funguje.
Spouštění: pytest tests/test_selenium.py -v
S výstupem prohlížeče: pytest tests/test_selenium.py -v --headed (v conftest lze vypnout headless)
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def _login(browser, username="admin", password="admin"):
    """Přihlásí uživatele na stránce /login."""
    browser.get(browser.base_url + "/login")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "username")))
    browser.find_element(By.ID, "username").send_keys(username)
    browser.find_element(By.ID, "password").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, "button[type=submit], input[type=submit], .btn-primary").click()


def test_login_page_loads(browser):
    """Stránka přihlášení se načte a obsahuje formulář."""
    browser.get(browser.base_url + "/login")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
    assert "Přihlášení" in browser.page_source or "přihlášení" in browser.page_source.lower()
    assert browser.find_element(By.ID, "username").is_displayed()
    assert browser.find_element(By.ID, "password").is_displayed()


def test_login_success_redirects_to_admin(browser):
    """Po přihlášení admin/admin se přesměruje na admin dashboard."""
    _login(browser, "admin", "admin")
    WebDriverWait(browser, 10).until(EC.url_contains("/admin"))
    assert "/admin" in browser.current_url
    assert "Admin" in browser.page_source or "admin" in browser.page_source.lower() or "Objednávk" in browser.page_source


def test_login_invalid_shows_error(browser):
    """Špatné přihlašovací údaje zobrazí chybu."""
    browser.get(browser.base_url + "/login")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "username")))
    browser.find_element(By.ID, "username").send_keys("wrong")
    browser.find_element(By.ID, "password").send_keys("wrong")
    browser.find_element(By.CSS_SELECTOR, "button[type=submit], input[type=submit], .btn-primary").click()
    WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".flash, .flash-error, [class*='flash']")))
    assert "Neplatné" in browser.page_source or "chyb" in browser.page_source.lower() or "error" in browser.page_source.lower()


def test_index_requires_login(browser):
    """Bez přihlášení / přesměruje na /login."""
    browser.get(browser.base_url + "/")
    WebDriverWait(browser, 10).until(lambda d: "/login" in d.current_url or "Přihlášení" in d.page_source)
    assert "/login" in browser.current_url


def test_admin_products_after_login(browser):
    """Po přihlášení je dostupná stránka Admin – Produkty."""
    _login(browser, "admin", "admin")
    browser.get(browser.base_url + "/admin/products")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
    assert "Produkt" in browser.page_source or "produkt" in browser.page_source.lower()
    assert "Admin" in browser.page_source or "admin" in browser.page_source


def test_admin_import_page(browser):
    """Stránka Admin – Import se načte."""
    _login(browser, "admin", "admin")
    browser.get(browser.base_url + "/admin/import")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
    assert "Import" in browser.page_source or "import" in browser.page_source.lower()
    # Formulář pro soubor
    file_input = browser.find_elements(By.CSS_SELECTOR, "input[type=file]")
    assert len(file_input) >= 1


def test_logout(browser):
    """Po odhlášení se uživatel dostane na /login."""
    _login(browser, "admin", "admin")
    WebDriverWait(browser, 5).until(EC.url_contains("/admin"))
    browser.get(browser.base_url + "/logout")
    WebDriverWait(browser, 10).until(lambda d: "/login" in d.current_url)
    assert "/login" in browser.current_url
    # Po odhlášení / vyžaduje znovu přihlášení
    browser.get(browser.base_url + "/")
    WebDriverWait(browser, 5).until(lambda d: "/login" in d.current_url)
    assert "/login" in browser.current_url


def test_admin_orders_page(browser):
    """Stránka Admin – Objednávky se načte."""
    _login(browser, "admin", "admin")
    browser.get(browser.base_url + "/admin/orders")
    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    assert "Objednávk" in browser.page_source or "objednávk" in browser.page_source.lower()
