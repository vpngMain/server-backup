# -*- coding: utf-8 -*-
"""
Fixtures pro E2E testy – Selenium driver a base URL.
Spusťte aplikaci před testy: python run_waitress.py (nebo flask run)
Používá Selenium Manager (Selenium 4.6+) pro automatické stažení ChromeDriver
odpovídajícího nainstalované verzi Chrome/Chromium.
"""
import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def _get_base_url():
    return os.environ.get("BASE_URL", "http://localhost:8081").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    return _get_base_url()


@pytest.fixture
def driver():
    """Selenium WebDriver – Chrome/Chromium. Driver stáhne Selenium Manager (verze dle prohlížeče)."""
    options = Options()
    if os.environ.get("HEADLESS", "1") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Bez Service() – Selenium 4.6+ stáhne správný ChromeDriver pro aktuální Chrome/Chromium
    d = webdriver.Chrome(options=options)
    d.implicitly_wait(10)
    try:
        yield d
    finally:
        d.quit()


@pytest.fixture
def logged_in_driver(driver, base_url):
    """Driver s přihlášeným adminem (PIN 0000)."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    driver.get(f"{base_url}/admin/login")
    pin_input = driver.find_element(By.ID, "pin")
    pin_input.clear()
    pin_input.send_keys("0000")
    driver.find_element(By.ID, "loginForm").submit()
    # Počkáme, až zmizí login stránka
    WebDriverWait(driver, 10).until(lambda d: "admin/login" not in d.current_url)
    return driver
