# Bezpečnostní a stabilní audit – Odběry (odberos)

**Datum auditu:** únor 2025  
**Scope:** celý projekt (app.py, šablony, konfigurace, závislosti)

---

## Shrnutí

Projekt byl zkontrolován z hlediska **bezpečnosti**, **stability** a **správného chování**. Níže jsou výsledky a provedené úpravy.

---

## Bezpečnost – co je v pořádku

| Oblast | Stav |
|--------|------|
| **Autentizace** | Hesla hashovaná (Werkzeug), PIN, role admin/user |
| **Autorizace** | `can_access_pobocka()`, admin-only routes chráněné kontrolou `is_admin()` |
| **CSRF** | Flask-WTF CSRF zapnuté, token v šablonách |
| **SQL injection** | SQLAlchemy ORM + parametrizované dotazy (`db.text(..., params)`), žádné slepování SQL z requestu |
| **XSS** | Žádné `\|safe` v šablonách – Jinja2 auto-escaping zapnutý |
| **Open redirect** | `_is_safe_redirect_url()` – redirect jen na relativní URL |
| **Session** | HTTPOnly, SameSite=Lax, Secure v produkci (nebo s ALLOW_HTTP_SESSION pro Tailscale) |
| **Konfigurace** | SECRET_KEY a DATABASE_URL z env, varování při defaultním klíči |

---

## Provedené opravy

### 1. Audit log – PIN v záznamu

- **Problém:** Při přidání uživatele se do tabulky `Akce` zapisoval text „Přidán uživatel: X (PIN: 1234)“ – PIN v audit logu.
- **Úprava:** Do záznamu se už nezapisuje PIN, pouze „Přidán uživatel: {jméno}“.

### 2. Model Akce – admin záznamy a cizí klíče

- **Problém:** Pro čistě admin akce (přidání uživatele, smazání pobočky atd.) se používalo `odber_id=0` a `pobocka_id=0`. V PostgreSQL by to při zapnutých FK mohlo selhat (žádný odber/pobočka s id=0).
- **Úprava:**
  - V modelu `Akce` jsou `odber_id` a `pobocka_id` nyní **nullable** (admin/systémové záznamy).
  - V kódu se pro admin akce používá `odber_id=None` a `pobocka_id=_system_pobocka_id()` (první pobočka) nebo konkrétní `pobocka_id` tam, kde dává smysl.
  - Pro existující SQLite DB byla doplněna **migrace**: přecreování tabulky `akce` s nullable sloupci (běží jen pokud jsou sloupce zatím NOT NULL).

### 3. Holé `except:` v migrate_db a jinde

- **Problém:** `except:` chytá i `KeyboardInterrupt`/`SystemExit` a skrývá skutečné chyby.
- **Úprava:** Všechny výskyty nahrazeny za `except Exception:` a kde je to vhodné, se chyby logují nebo rollbackuje session.

---

## Stabilita a funkčnost

| Oblast | Stav |
|--------|------|
| **Teardown** | `shutdown_session` po každém requestu volá `db.session.remove()` a při výjimce `rollback()` |
| **Error handlery** | 404, 403, 500 s vlastními handlery a rollback u 500 |
| **Health check** | `/health` testuje připojení k DB, vrací 200/503 |
| **Formuláře** | WTForms s Length/Regexp/DataRequired, dodatečná validace (telefon 9 číslic, záruka 2 roky u reklamací) |
| **Exporty** | CSV/Excel s try/except a rollback při chybách |
| **Migrace DB** | `migrate_db()` pouze pro SQLite, PostgreSQL používá create_all; migrace jsou idempotentní |

---

## Doporučení do budoucna

1. **Rate limiting** – zvážit u přihlašovacího endpointu a veřejných API (např. Flask-Limiter).
2. **Záloha DB** – pravidelné zálohy (cron) – viz TAILSCALE_DEPLOYMENT.md.
3. **Změna výchozího admina** – po prvním přihlášení změnit PIN a heslo (dokumentováno).
4. **Závislosti** – občas spustit `pip audit` nebo kontrolovat CVE u Flask/Werkzeug atd.

---

## Soubory změněné v rámci auditu

- `site/app.py` – model Akce (nullable), helper `_system_pobocka_id()`, nahrazení odber_id/pobocka_id=0 za None/resp. systémové ID, odstranění PIN z audit logu, bare `except` → `except Exception`, migrace tabulky `akce` pro SQLite.

---

**Závěr:** Aplikace je z hlediska bezpečnosti a stability v dobrém stavu. Provedené úpravy zlepšují bezpečnost (nelogování PINu), kompatibilitu s PostgreSQL a předvídatelné chování při chybách (správné zacházení s výjimkami a migracemi).
