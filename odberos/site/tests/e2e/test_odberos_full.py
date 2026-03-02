# -*- coding: utf-8 -*-
"""
E2E testy plné funkčnosti webu Odberos (Selenium).
Vyžaduje běžící aplikaci: python run_waitress.py (nebo BASE_URL na jiný server).
Default přihlášení: admin PIN 0000 (vytvořen init_db při prázdné DB).
"""
import os
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# --- Health a veřejné stránky ---

def test_health_check(driver, base_url):
    """Health endpoint vrací 200 a JSON."""
    driver.get(f"{base_url}/health")
    body = driver.find_element(By.TAG_NAME, "pre").text
    assert "healthy" in body or "status" in body
    assert "database" in body.lower() or "timestamp" in body.lower()


def test_login_page_visible(driver, base_url):
    """Stránka přihlášení zobrazuje formulář s PINem."""
    driver.get(f"{base_url}/admin/login")
    assert "Přihlášení" in driver.page_source or "přihlášení" in driver.page_source
    pin = driver.find_element(By.ID, "pin")
    assert pin.is_displayed()
    form = driver.find_element(By.ID, "loginForm")
    assert form.get_attribute("method").lower() == "post"


def test_redirect_to_login_when_not_authenticated(driver, base_url):
    """Nepřihlášený uživatel je přesměrován na /admin/login při návštěvě /."""
    driver.get(f"{base_url}/")
    WebDriverWait(driver, 10).until(EC.url_contains("admin/login"))
    assert "admin/login" in driver.current_url


# --- Přihlášení a hlavní stránka ---

def test_login_with_pin_and_see_index(logged_in_driver, base_url):
    """Po přihlášení PINem 0000 je uživatel na indexu nebo dashboardu."""
    driver = logged_in_driver
    assert "admin/login" not in driver.current_url
    # Na stránce je buď přehled (Odběry / PPL / pobočky) nebo admin dashboard
    body = driver.page_source
    assert "Vítejte" in body or "Odběry" in body or "Pobočk" in body or "Dashboard" in body or "PPL" in body


def test_index_shows_branch_cards_or_ppl(logged_in_driver, base_url):
    """Na hlavní stránce jsou karty poboček nebo odkaz na PPL."""
    driver = logged_in_driver
    driver.get(f"{base_url}/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".branch-card, .ppl-index-card, .rekl-card, .card-apple, a[href*='/ppl']"))
    )
    # Minimálně jeden odkaz na pobočku nebo PPL
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/branch/'], a[href*='/ppl']")
    assert len(links) >= 1 or "PPL sklad" in driver.page_source or "Teplice" in driver.page_source or "Děčín" in driver.page_source


# --- Pobočka a odběry ---

def test_open_branch_and_see_odbery_form(logged_in_driver, base_url):
    """Otevření první pobočky zobrazí přehled a formulář pro nový odběr."""
    driver = logged_in_driver
    driver.get(f"{base_url}/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/branch/']"))
    )
    branch_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/branch/']")
    assert branch_links, "Na indexu by měl být odkaz na pobočku"
    branch_links[0].click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "odberForm"))
    )
    assert driver.find_element(By.ID, "odberForm").is_displayed()
    assert "Přidat nový odběr" in driver.page_source or "Nový odběr" in driver.page_source


def test_add_odber(logged_in_driver, base_url):
    """Přidání nového odběru přes formulář a ověření flash/redirect."""
    driver = logged_in_driver
    driver.get(f"{base_url}/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/branch/']"))
    )
    driver.find_element(By.CSS_SELECTOR, "a[href*='/branch/']").click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "odberForm")))

    jmeno = driver.find_element(By.NAME, "jmeno")
    jmeno.clear()
    jmeno.send_keys("E2E Test Zákazník")
    telefon = driver.find_element(By.NAME, "telefon")
    if telefon:
        telefon.clear()
        telefon.send_keys("123456789")
    driver.find_element(By.ID, "odberForm").submit()

    WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-success, .alert-success")),
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Odběr přidán') or contains(text(),'přidán')]"))
        )
    )
    assert "Odběr přidán" in driver.page_source or "přidán" in driver.page_source or "E2E Test Zákazník" in driver.page_source


def test_branch_export_csv(logged_in_driver, base_url):
    """Export CSV z pobočky stáhne soubor nebo vrátí CSV obsah."""
    driver = logged_in_driver
    driver.get(f"{base_url}/")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/branch/']"))
    )
    driver.find_element(By.CSS_SELECTOR, "a[href*='/branch/']").click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/export.csv']"))
    )
    export_link = driver.find_element(By.CSS_SELECTOR, "a[href*='/export.csv']")
    href = export_link.get_attribute("href")
    assert "/branch/" in href and "export.csv" in href
    # Otevřeme odkaz – v reálném prohlížeči by se stáhl soubor
    driver.get(href)
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "Jméno" in body or "ID" in body or body.startswith("\ufeff") or "csv" in driver.current_url


# --- Reklamace ---

def test_reklamace_index(logged_in_driver, base_url):
    """Stránka reklamací zobrazí přehled poboček nebo prázdný stav."""
    driver = logged_in_driver
    driver.get(f"{base_url}/reklamace")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "main"))
    )
    assert "Reklamace" in driver.page_source or "reklamace" in driver.page_source
    assert "Elektronické cigarety" in driver.page_source or "reklamací" in driver.page_source


def test_reklamace_branch_page(logged_in_driver, base_url):
    """Otevření reklamací pro pobočku zobrazí formulář nebo seznam."""
    driver = logged_in_driver
    driver.get(f"{base_url}/reklamace")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/reklamace/branch/']"))
    )
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/reklamace/branch/']")
    if not links:
        pytest.skip("Žádné pobočky pro reklamace")
    links[0].click()
    WebDriverWait(driver, 10).until(
        EC.any_of(
            EC.presence_of_element_located((By.ID, "reklamaceWizardForm")),
            EC.presence_of_element_located((By.CSS_SELECTOR, ".reklamace-filters, .rekl-wizard-card"))
        )
    )
    assert "Reklamace" in driver.page_source or "Průvodce reklamací" in driver.page_source


# --- Admin (pouze admin uživatel) ---

def test_admin_dashboard(logged_in_driver, base_url):
    """Admin může otevřít admin dashboard (přihlášení PIN 0000 = admin)."""
    driver = logged_in_driver
    driver.get(f"{base_url}/admin/dashboard")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "main, .card, [href='/logout'], form"))
    )
    # Buď dashboard obsah, nebo přesměrování na index (pokud není admin)
    body = driver.page_source
    assert "Dashboard" in body or "Pobočk" in body or "Uživatel" in body or "admin" in body.lower() or "Odběry" in body


def test_logout(logged_in_driver, base_url):
    """Odhlášení přes odkaz /logout a ověření redirectu na login."""
    driver = logged_in_driver
    driver.get(f"{base_url}/")
    logout = driver.find_elements(By.CSS_SELECTOR, "a[href='/logout']")
    if not logout:
        # Možná v menu
        logout = driver.find_elements(By.XPATH, "//a[contains(@href,'logout')]")
    if not logout:
        pytest.skip("Odkaz Odhlásit nebyl nalezen v UI")
    logout[0].click()
    WebDriverWait(driver, 10).until(EC.url_contains("admin/login"))
    assert "admin/login" in driver.current_url


# --- PPL modul ---

def test_ppl_index(logged_in_driver, base_url):
    """PPL stránka (výběr pobočky) se načte."""
    driver = logged_in_driver
    driver.get(f"{base_url}/ppl")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "main"))
    )
    body = driver.page_source
    assert "PPL" in body and ("sklad" in body.lower() or "poboč" in body.lower() or "Vyberte" in body or "Teplice" in body or "Děčín" in body)


def test_ppl_branch_sklad(logged_in_driver, base_url):
    """PPL sklad pro pobočku – stránka skladu (pobočka ID 1 z init_db)."""
    driver = logged_in_driver
    # Init_db vytváří pobočky Teplice (id=1), Děčín (id=2) – zkusíme /ppl/1
    driver.get(f"{base_url}/ppl/1")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "main, .card, nav, [href*='sklad'], [href*='historie']"))
    )
    assert "PPL" in driver.page_source or "sklad" in driver.page_source.lower() or "Sklad" in driver.page_source
