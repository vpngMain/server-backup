# Checklist před spuštěním v produkci

## ✅ Co je v kódu v pořádku

| Položka | Stav |
|--------|------|
| **Debug** | `debug=False` při spuštění přes `app.run` |
| **CSRF** | Zapnuto, časový limit 1 h |
| **Session** | HTTPOnly, SameSite=Lax, Secure v produkci (nebo ALLOW_HTTP_SESSION pro HTTP) |
| **Hesla** | Hashování přes Werkzeug |
| **Chybové stránky** | 400, 403, 404, 500 s vlastní šablonou a fallback HTML |
| **POST/GET** | Bezpečné čtení `request.form` a `request.get_json(silent=True)` |
| **Formuláře** | Ošetřená `form.*.data` proti None |
| **Health endpoint** | `GET /health` pro monitoring |

---

## ⚠️ Před spuštěním na serveru

1. **SECRET_KEY**  
   Na serveru **nastav** proměnnou prostředí (nechávej default jen pro vývoj):
   ```bash
   # Vygenerovat: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   export SECRET_KEY="váš-vygenerovaný-klíč"
   ```
   V systemd: v souboru `odberos.env` řádek `SECRET_KEY=...`.

2. **Tailscale / pouze HTTP**  
   Pokud běžíš přes HTTP (např. `http://100.x.x.x:8080`):
   ```bash
   export ALLOW_HTTP_SESSION=1
   ```
   Jinak session cookie se nebude posílat a přihlášení nebude držet.

3. **Databáze**  
   - SQLite: stačí že proces má právo zapisovat do složky se souborem `odbery.db`.  
   - PostgreSQL: nastav `DATABASE_URL` na celý connection string.

4. **Admin účet**  
   Po prvním přihlášení změň výchozí PIN a heslo (admin / 0000 / admin123).

---

## Spuštění

- **Přes app.py:** `python app.py` (načte .env pokud je a máš python-dotenv).
- **Přes Waitress:** `python run_waitress.py`.
- **Systemd:** služba `odberos` s `EnvironmentFile=.../odberos.env`.

Aplikace je na produkci připravená za předpokladu, že na serveru nastavíš **SECRET_KEY** a u HTTP přístupu **ALLOW_HTTP_SESSION=1**.
