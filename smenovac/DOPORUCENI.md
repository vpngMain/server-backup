# Doporučení na vylepšení

## ✅ Už implementováno

### Reset databáze (fresh start)
- **`python reset_db.py`** – smaže všechny tabulky, znovu je vytvoří a přidá demo účet (demo@demo.cz / demo). Spusť před prvním spuštěním nebo když chceš databázi vrátit „od nuly“.

### E-mail notifikace
- **Admin** dostane mail při nové žádosti (volno, zpoždění)
- **Zaměstnanec** dostane mail při schválení/zamítnutí žádosti
- **Zaměstnanec** dostane mail při nové/změněné směně *(potřebuje e-mail u zaměstnance nebo propojený účet)*
- Konfigurace: `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` v `.env`
- **APP_URL** – veřejná adresa aplikace pro odkazy v e-mailu. Bez ní se používá localhost (127.0.0.1), což **nefunguje na telefonu** – odkaz v mailu nelze otevřít! Nastav např. `APP_URL=https://vase-domena.cz`
- `MAIL_DEBUG=1` – vypíše chyby odeslání a kdy chybí e-mail u zaměstnance

---

## Další možná vylepšení

### Notifikace (rozšíření)
- **Připomínka směny** – „Zítra máte směnu 8–14“ (den předem)
- **Nový přiřazená směna** – když admin přidá zaměstnanci směnu
- **Změna směny** – když admin upraví existující směnu

### Funkce
- **Mobilní PWA** – přidat `manifest.json` a service worker pro „přidat na plochu“
- **Potvrzení akcí** – např. „Opravdu smazat?“ u kritických akcí (už částečně je)
- **Historie změn** – kdo kdy co změnil (audit log)
- **Export do PDF** – rozvrh na týden/měsíc
- **iCal export** – pro import do Google kalendáře, Outlook
- **Tisk rozvrhu** – optimalizovaná stránka pro tisk

### Bezpečnost
- **Rate limiting** – omezení pokusů o přihlášení
- **CSRF ochrana** – Flask-WTF pro formuláře (API používá JSON, méně kritické)
- **Zakázat registraci** – env `ALLOW_REGISTRATION=0` pro uzavřený tým

### UX
- **Dark mode** – přepínač světlý/tmavý režim
- **Oznámení v app** – toast/zpráva „Žádost odeslána“ místo alert()
- **Načítání** – skeleton/loader při fetchích

### Technické
- **Caching** – Redis pro session nebo časté dotazy (u SQLite zatím OK)
- **Logging** – strukturované logy do souboru
- **Health endpoint** – `/health` pro monitoring ✅ *(implementováno – vrací status + database)*
