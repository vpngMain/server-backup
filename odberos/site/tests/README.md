# E2E testy (Selenium)

Testy plné funkčnosti webu – přihlášení, pobočky, odběry, reklamace, admin, PPL, export CSV, odhlášení.

## Požadavky

- Python 3.x, Chrome (Chromium)
- Běžící aplikace na `http://localhost:8080` (nebo nastavte `BASE_URL`)

## Instalace

```bash
cd site
pip install -r requirements-test.txt
```

## Spuštění

1. V jednom terminálu spusťte aplikaci:
   ```bash
   cd site
   python run_waitress.py
   ```

2. V druhém terminálu spusťte testy:
   ```bash
   cd site
   pytest tests/e2e/ -v
   ```

## Proměnné prostředí

| Proměnná    | Význam                          | Výchozí              |
|------------|----------------------------------|----------------------|
| `BASE_URL` | URL běžící aplikace              | `http://localhost:8080` |
| `HEADLESS` | `1` = Chrome v headless režimu  | `0`                  |

Příklad:

```bash
BASE_URL=http://127.0.0.1:8080 HEADLESS=1 pytest tests/e2e/ -v
```

## Přihlášení v testech

Testy používají výchozího admina vytvořeného při prvním spuštění (prázdná DB): **PIN `0000`** (uživatel `admin`, heslo `admin123`).

## Co testy pokrývají

- Health endpoint (`/health`)
- Stránka přihlášení a přesměrování nepřihlášeného
- Přihlášení PINem a zobrazení hlavní stránky
- Karty poboček na indexu
- Otevření pobočky a formulář „Přidat odběr“
- Přidání nového odběru a ověření hlášky
- Export CSV z pobočky
- Stránka reklamací a reklamace pro pobočku
- Admin dashboard
- Odhlášení
- PPL modul (výběr pobočky, sklad)
