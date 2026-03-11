# Blooms – popis aplikace pro ChatGPT

Krátký kontext o aplikaci, aby AI asistent mohl lépe pomáhat s kódem a rozšířeními.

---

## Co to je

**Blooms** je interní webová aplikace pro zahradnictví (Flask, Python 3.12+). Slouží k importu produktů z Excelu (.xls/.xlsx), správě produktů a odběratelů, vystavování dodacích listů (tisk, PDF) a základnímu reportingu. Běží lokálně (SQLite), přihlášení přes DB (admin/user).

---

## Stack

| Vrstva | Technologie |
|--------|-------------|
| Backend | Flask |
| Šablony | Jinja2 |
| UI | Bootstrap 5, HTMX (live search, dynamické části) |
| DB | SQLAlchemy 2, Alembic, SQLite |
| Import | xlrd (.xls), openpyxl (.xlsx) |
| PDF | reportlab |
| Hesla | bcrypt |

---

## Hlavní funkce

1. **Import produktů** – upload .xls/.xlsx; doprava (EUR) a kurz (pro VIP CZK, D1) volitelně. Produkty se identifikují podle **Description + Pot-Size** (normalizovaný klíč). Po importu přesměrování na kontrolu: porovnání cen s DB, zvýraznění rozdílů, editace cen a uložení do produktu. Řádky (po řádcích): část sloupců jen na zobrazení (Description, Pot-Size, Qty, Sales Price, Amount…), editovatelné jsou jen **ceny a EAN** (Cena+doprava, 7% marže+doprava, VIP Eur, VIP CZK, D1, D4, EAN).
2. **Produkty** – seznam, filtr, live search (HTMX), detail s cenami (Sales Price, Cena+doprava, 7% marže, VIP Eur/CZK, D1, D4), přepisy cen (override). Cenové hladiny: VIP_EUR, VIP_CZK, D1 (obchod), D4.
3. **Odběratelé** – CRUD, import z ARES (IČO / obchodní název), přiřazení cenové hladiny.
4. **Dodací listy** – vytvoření, položky z produktů (nebo ruční), filtry (status, datum od–do, odběratel, číslo dokladu), tisk, PDF.
5. **Uživatelé** – admin/user, změna hesla (admin).
6. **Statistiky** – dashboard s grafy (Chart.js): tržby po odběratelích, množství po produktech, dodací listy po měsících).
7. **Audit log** – záznam vybraných akcí.

---

## Důležité modely (DB)

- **Product** – description, description2, pot_size, product_key_normalized; ceny *_imported a *_override (sales, purchase, margin_7, vip_eur, vip_czk, trade, d4); EAN, VBN, qty, unit_per_cc atd.
- **Customer** – company_name, ico, price_level (VIP_EUR, VIP_CZK, D1, D4).
- **DeliveryNote** – document_number, customer_id, issue_date, delivery_date, status (draft/issued), total_amount; položky **DeliveryNoteItem** (product_id, quantity, unit_price, line_total, is_manual_item).
- **ImportBatch** – source_folder, shipping_eur, exchange_rate, souhrn (total_rows, new_products, existing_products, error_rows).
- **ImportFile** – soubor v dávce, report_text (včetně mapování sloupců).
- **ImportRow** – raw_data_json (data řádku), matched_product_id, action_taken (new/matched/skipped/error).
- **User** – username, password_hash, role (admin/user).

---

## Import – vzorce cen (dopočty)

- **Cena + doprava (Purchase)** = sales_price + (doprava_eur / unit_per_cc)
- **7% marže + doprava** = (doprava_eur / unit_per_cc) + (sales_price × 1.07)
- **VIP Eur** = (cena + doprava) + (100 / unit_per_cc)
- **VIP CZK** = VIP Eur × volitelný kurz
- **D1 (cena obchod)** = (cena + doprava) × eurKurz × 1.12 × 2
- **D4** = průměr mezi **VIP CZK** a **Cena obchod (D1)**

Mapování sloupců z Excelu je tolerantní: mnoho aliasů (Description, Popis, Pot-Size, pot size…), normalizace hlaviček (tečky, závorky). Výsledné mapování je v reportu importu (Shrnutí a log).

---

## Struktura projektu (zkráceno)

```
app/
  config.py          # DATABASE_URL, SECRET_KEY, DEV_SKIP_AUTH
  db.py              # engine, SessionLocal, Base, utc_now
  models/            # Product, Customer, DeliveryNote, DeliveryNoteItem, ImportBatch, ImportFile, ImportRow, User, AuditLog
  flask_app/         # blueprinty: auth, main, products, customers, delivery, import, users; errors (404/500)
  services/          # import_parser, price_formulas (vzorce cen, D1/Purchase/VIP; D4 jen z importu), import_service (run_import, apply_import_to_products),
                     # delivery_note_service, pdf_service, stats_service, audit_service, ares_service
  templates/         # base.html, produkty, zákazníci, dodací listy, import (import.html, history, detail, file_detail, row_edit)
  utils/             # normalizer (product_key_normalized), loaders (get_*_or_404)
  auth/              # password (hash/verify), auth_service
alembic/             # migrace
resetdb.py           # drop_all + create_all
seed_db.py           # admin, 1 zákazník, 1 produkt
run_flask.py         # entrypoint
```

---

## Konvence a poznámky

- Produkt se identifikuje podle **product_key_normalized** = normalizovaný(description) + "::" + normalizovaný(pot_size).
- Ceny v produktu: *_imported z importu, *_override ruční přepis; efektivní cena = override ?? imported.
- CSRF: Flask-WTF, v šablonách `{% include '_csrf.html' %}`; v testech `WTF_CSRF_ENABLED = False`.
- Paginace: produkty 50/str., dodací listy 50/str.
- Odpovědi v češtině (flash, labely, chyby).
- Testy: pytest, `tests/test_ready_for_use.py`, fixture `seeded_db` / `logged_in_seeded_client`.

---

## Rychlý start (pro kontext)

```bash
pip install -r requirements.txt
python resetdb.py
python seed_db.py
python run_flask.py
# http://127.0.0.1:5000 , admin / admin
```

Tento soubor můžeš v chatu s ChatGPT vložit jako kontext před dotazy na kód nebo rozšíření Blooms.
