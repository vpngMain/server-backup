# Evidence hotovosti

Jednoduchá webová aplikace pro evidenci hotovosti (Obálka + Kasička) s rolemi Uživatel a Admin.

## Požadavky

- Python 3.10+
- pip

## Instalace

```bash
cd DPD
pip install -r requirements.txt
```

## Inicializace databáze

```bash
set FLASK_APP=app.py
flask init-db
```

Vytvoří se tabulky a výchozí data:
- Pobočky: Praha, Brno
- Uživatelé: Pepa (Praha), Evžen (Brno) – PIN **1234**
- Admin – PIN **0000**

## Spuštění

```bash
set FLASK_APP=app.py
flask run
```

V prohlížeči: http://127.0.0.0:5000

## Použití

1. **Přihlášení** – zadejte PIN (4–6 číslic).
2. **Uživatel**: sekce Obálka (bankovky 5000–100 Kč), Zbylo v kasičce (5000–1 Kč), tlačítko ULOŽIT, VYTISKNOUT OBÁLKU.
3. **Admin**: dashboard s tabulkou, filtry pobočka/týden, Export CSV.

Tisk obálky je optimalizovaný na šířku 62 mm (termotiskárna Brother).
