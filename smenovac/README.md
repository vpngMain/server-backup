# Vaping směnovač

Interní systém pro plánování směn. Python Flask + SQLite + HTML/CSS/JS. Plně responzivní, včetně mobilu.

## Spuštění

```bash
pip install -r requirements.txt
python app.py
```

Aplikace běží na http://127.0.0.1:5000

## Funkce

- **Registrace a přihlášení** – každý uživatel má své data
- **Směny** – přidávání směn, zobrazení dne a týdne
- **Kalendář** – týdenní nebo denní zobrazení
- **Pobočky** – správa poboček, výchozí hodinová sazba
- **Zaměstnanci** – přiřazení k pobočkám, individuální hodinová sazba
- **Presety** – šablony směn pro rychlé přidávání
- **Odpracované hodiny a orientační plat** – přehled hodin a vypočtený orientační plat
- **Kdo s kým** – překrývání směn
- **Export** – export směn a hodin/platů do CSV (vhodné pro Excel)

## Technologie

- Flask, SQLAlchemy, Flask-Login
- SQLite (soubor `smeny.db`)
- Čisté HTML, CSS, JavaScript
