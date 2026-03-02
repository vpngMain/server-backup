# Objednávač (Flask)

Interní systém pro objednávky ze skladu. Flask + HTML šablony + CSS + JS.

Název aplikace lze přepsat přes proměnnou prostředí: `APP_NAME=Moje firma` (výchozí: Objednávač).

## Požadavky

- Python 3.10+

## Spuštění

```powershell
cd c:\Users\vapin\Desktop\simple_objednavka
python -m venv venv_flask
venv_flask\Scripts\activate
pip install -r requirements-flask.txt
python app.py
```

V prohlížeči: **http://127.0.0.1:5000**  
Přihlášení: **admin** / **admin**

## Reset databáze

Smaže všechny tabulky a znovu je vytvoří (všechna data budou ztracena). Po resetu se vždy vytvoří výchozí admin (admin/admin):

```powershell
flask reset-db
```

Nebo Python skript (z kořene projektu):

```powershell
python scripts/reset_db.py
```

Bez vytvoření admina: `flask reset-db --no-seed` nebo `python scripts/reset_db.py --no-seed`

## Struktura (pouze potřeba pro běh)

```
simple_objednavka/
├── app.py              # Flask aplikace
├── requirements-flask.txt
├── warehouse.db        # vytvoří se při prvním spuštění
├── scripts/
│   └── reset_db.py     # reset databáze (python scripts/reset_db.py)
├── templates/          # HTML šablony
├── static/
│   ├── css/style.css
│   └── js/main.js
└── uploads/            # import souborů (dočasně)
```

## Nasazení (Gunicorn)

Při velkém importu produktů (stovky až tisíce řádků) může request překročit výchozí timeout Gunicornu (30 s). Nastavte vyšší timeout, např.:

```bash
gunicorn -w 3 -b 0.0.0.0:8082 --timeout 300 "app:app"
```

Import nyní ukládá každý řádek zvlášť (commit po řádku), takže při přerušení zůstanou alespoň již zpracované řádky. CSV s tabulátorem (TSV) je podporováno automaticky.

## Testování (pytest + Selenium + Chromium/Chrome)

Automatické testy ověří přihlášení, stránky adminu a odhlášení v reálném prohlížeči (headless Chrome/Chromium).

```powershell
pip install -r requirements-test.txt
pytest tests/ -v
```

Vyžaduje nainstalovaný **Chrome** nebo **Chromium**; `webdriver-manager` stáhne odpovídající ChromeDriver. Pro zobrazení okna prohlížeče lze v `tests/conftest.py` dočasně vypnout `--headless`.

## Odstranění starého React/FastAPI

Složky **backend** a **frontend** už nejsou potřeba. Smazat je můžeš ručně:

1. Zavři všechny otevřené soubory z těchto složek v editoru.
2. V Průzkumníku smaž složky `backend` a `frontend`.
3. Případně smaž i složku `venv` (staré Python prostředí), pokud používáš jen `venv_flask`.
