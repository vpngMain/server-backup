# Blooms – interní firemní systém zahradnictví

Lokální webová aplikace pro:
- **Import produktů** z .xls souborů ze zvolené složky
- **Správu produktů** (identifikace dle Description + Pot-Size)
- **Správu odběratelů**
- **Dodací listy** (vytvoření, tisk, export do PDF)
- **Lokální přihlášení** (uživatelé v DB, role admin/user)

## Stack

- **Python 3.12+**
- **Flask** – backend
- **Jinja2** – šablony
- **HTMX** – dynamické části UI
- **Bootstrap 5** – vzhled (CDN)
- **SQLAlchemy 2** + **Alembic** – ORM a migrace
- **SQLite** – databáze
- **xlrd** – čtení skutečných .xls souborů (binární XLS, ne .xlsx)
- **reportlab** – generování PDF (čistý Python, bez externích binárek na Windows)
- **bcrypt** – hash hesel (přímo, bez passlib)

## Instalace (Windows)

1. **Python 3.12+**  
   Ověřte: `python --version` nebo `py -3.12 --version`.

2. **Vytvoření virtuálního prostředí**
   ```bat
   cd C:\Users\...\blooms
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Instalace závislostí**
   ```bat
   pip install -r requirements.txt
   ```

4. **Databáze**
   - **Nový projekt / reset:** `python resetdb.py` (smaže tabulky a vytvoří je z modelů). Volitelně `python resetdb.py --stamp` pro označení migrací.
   - **Migrace:** `alembic upgrade head` (vytvoří/aktualizuje `blooms.db` v kořeni projektu).

5. **Seed (výchozí data)**
   ```bat
   python seed_db.py
   ```
   Vytvoří uživatele **admin** / **admin**, jednoho zákazníka a jeden produkt (idempotentní). Alternativa jen pro admina: `python scripts/seed_admin.py`.

6. **Spuštění aplikace**
   ```bat
   python run_flask.py
   ```
   V prohlížeči: **http://127.0.0.1:5000**

## Přihlášení

- **Výchozí účet:** `admin` / `admin`
- **Důležité:** Po prvním přihlášení změňte heslo v sekci **Uživatelé** (pouze admin). Výchozí heslo je pouze pro první nastavení.

## Změna výchozího hesla

1. Přihlaste se jako **admin**.
2. V menu zvolte **Uživatelé**.
3. Klikněte **Upravit** u uživatele **admin**.
4. Zadejte nové heslo a uložte.

## Testy

**Heavy testy** (ověření, že je aplikace ready for use – auth, produkty, odběratelé, dodací listy, import, uživatelé, 404, audit, statistiky):

```bat
cd C:\cesta\k\blooms
python -m pytest tests/test_ready_for_use.py -v
```

Z adresáře `tests`:

```bat
cd blooms\tests
python -m pytest test_ready_for_use.py -v
```

Všechny testy v projektu: `python -m pytest tests/ -v`

## Struktura projektu

```
app/
  flask_app/       # Flask blueprinty (auth, main, products, customers, delivery, import, users)
  config.py
  db.py
  models/          # SQLAlchemy modely
  services/        # import_parser, import_service, delivery_note_service, pdf_service, ares_service
  templates/
  static/
  utils/           # normalizer
alembic/
scripts/
  seed_admin.py
run_flask.py       # Spuštění: python run_flask.py
requirements.txt
README.md
```

## ASSUMPTIONS (předpoklady)

- **Identifikace produktu** = Description + Pot-Size (oba normalizované). Description 2 je pouze doplňkový popis.
- **Ceny** z importu se pouze ukládají (sales_price_imported, trade_price_imported atd.), obchodní logika a cenotvorba se v první verzi neřeší.
- **Import** čte pouze soubory .xls v zadané složce; podsložky se neprohledávají.
- **Skladové pohyby** a **cenotvorba** se v první verzi neřeší.
- **Číslování dodacích listů** je automatické (DL-YYYY-0001).
- **Ruční položka** na dodacím listu může být v budoucnu uložena jako nový produkt (UI připraveno, logika „uložit jako produkt“ může být doplněna).
- **Autentizace** je lokální přes databázi (session se ukládá do souborů v `instance/flask_session`).
- Aplikace je určena pro **rychlé interní použití** na Windows.

## Známá omezení první verze

- Při importu se nečtou podsložky, pouze zadaná složka.
- Session je v paměti – po restartu serveru jsou uživatelé odhlášeni.
- PDF export používá reportlab (bez externích binárek); pro složitější layout lze později zvážit WeasyPrint (na Windows může vyžadovat GTK).
- Jedno číslo objednávky z názvu souboru – pokud je v názvu více čísel, použije se první vyhovující vzor.

## Import .xls

- Na stránce **Import** zadejte cestu ke složce (např. `C:\Data\objednavky`).
- Systém načte všechny soubory s příponou **.xls** v této složce (pouze první list v sešitu).
- Očekávané sloupce (názvy se mapují tolerantně): Description, Description 2, Pot-Size, Qty., Ordered Qty., Per Unit, Sales Price, Amount, EAN Code, VBN Code, Plant Passport No., Customer Line Info, Image Reference, Cena + doprava, 7% marže + doprava, VIP CZK, Cena obchod atd.
- Chybějící sloupce nezpůsobí pád; řádky bez Description se přeskočí a zapíší do reportu.

## Spuštění na Windows (shrnutí)

```bat
cd C:\Users\...\blooms
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_admin.py
python run_flask.py
```

Otevřete **http://127.0.0.1:5000**, přihlaste se jako **admin** / **admin** a změňte heslo.

## Doporučení ke zdokonalení

Náměty na vylepšení aplikace (prioritně podle dopadu a náročnosti):

### Bezpečnost a provoz
- **SECRET_KEY v produkci** – nastavit `SECRET_KEY` z prostředí (např. dlouhý náhodný řetězec), nikdy nepoužívat výchozí `blooms-internal-dev-change-in-production`.
- **CSRF ochrana** – u formulářů s POST (import, úpravy produktů, odběratelů, dodacích listů) zvážit Flask-WTF nebo vlastní CSRF token, aby šlo zabránit cross-site request forgery.
- **Session v produkci** – při více workerech zvážit sdílené úložiště session (např. Redis); aktuálně session v souborech stačí pro jeden proces.

### Uživatelská zkušenost
- **Flash zprávy** – po uložení formuláře („Změny uloženy“), po importu („Import dokončen“) nebo při chybě zobrazit krátkou hlášku nahoře na stránce (Bootstrap alert).
- **Globální stránky chyb** – vlastní šablony pro 404 a 500 (`@app.errorhandler(404)` / `500`) s odkazem na dashboard, aby uživatel nedostal holou Flask stránku.
- **Potvrzení před smazáním** – u akcí „smazat položku“, „zrušit dodací list“ atd. přidat `confirm()` v JS nebo Bootstrap modal.

### Výkon a škálování
- **Paginace** – u seznamu produktů (limit 500) a dodacích listů zvážit stránkování (např. 50/100 na stránku), aby se zbytečně nenačítalo vše.
- **Indexy v DB** – ověřit indexy na často filtrované sloupce (např. `delivery_notes.issue_date`, `delivery_notes.customer_id`, `products.active`); Alembic migrace je mohou přidat.

### Testování a kvalita kódu
- **Testy Flask rout** – kromě stávajících testů (import parser, normalizer) přidat integrační testy pro klíčové endpointy: přihlášení, seznam produktů, vytvoření dodacího listu (pytest + test client).
- **Validace vstupů** – u cest s parametrem (např. `product_id`, `customer_id`) ověřovat typ a existenci záznamu na jednom místě; při neplatném ID vracet 404.

### Funkční rozšíření
- **Export seznamu produktů** – tlačítko „Export do CSV/Excel“ na stránce Produkty pro reporting.
- **Historie změn** – u produktů nebo dodacích listů evidovat „kdy a kdo změnil“ (audit log), pokud to interní pravidla vyžadují.
- **Import podsložek** – volitelné prohledávání podsložek při importu .xls (podle README zatím jen jedna složka).

Můžeš postupně vybírat body podle potřeby; největší přínos pro běžný provoz mají SECRET_KEY, flash zprávy a vlastní 404/500 stránky.
