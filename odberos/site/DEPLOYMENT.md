# 🚀 Návod pro nasazení na PythonAnywhere

## ✅ Checklist před nasazením

### 1. Konfigurace aplikace
- ✅ `SECRET_KEY` - nastaveno přes `os.environ.get()` (bezpečné)
- ✅ `DATABASE_URL` - nastaveno přes `os.environ.get()` (flexibilní)
- ✅ `debug=False` - produkční režim
- ✅ Error handling - všechny routes mají try-except bloky
- ✅ Migrace databáze - automatické při startu

### 2. Závislosti
- ✅ `requirements.txt` - kompletní seznam všech balíčků
- ✅ Všechny importy mají fallback pro volitelné balíčky (openpyxl)

### 3. Bezpečnost
- ✅ Hesla hashované pomocí Werkzeug
- ✅ PIN autentizace implementována
- ✅ Role-based access control (admin/user)
- ✅ Branch-based access control

## 📋 Postup nasazení na PythonAnywhere

### Krok 1: Nahrání souborů
1. Nahrajte všechny soubory do adresáře na PythonAnywhere:
   ```
   /home/yourusername/odberos/site/
   ```

2. Struktura souborů:
   ```
   site/
   ├── app.py
   ├── wsgi.py
   ├── requirements.txt
   ├── templates/
   │   ├── base.html
   │   ├── index.html
   │   ├── admin_*.html
   │   └── ...
   ├── static/
   │   └── main.js
   └── instance/
       └── odbery.db (vytvoří se automaticky)
   ```

### Krok 2: Instalace závislostí
V Bash konzoli na PythonAnywhere:
```bash
cd /home/yourusername/odberos/site
pip3.10 install --user -r requirements.txt
```

**Poznámka:** Použijte správnou verzi Pythonu (např. `pip3.10` pro Python 3.10)

### Krok 3: Konfigurace WSGI
1. Otevřete WSGI konfigurační soubor v PythonAnywhere dashboardu
2. Odstraňte výchozí obsah
3. Vložte:
```python
import sys
path = '/home/yourusername/odberos/site'  # ZMĚŇTE na vaši cestu
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application
```

**Nebo použijte připravený `wsgi.py` soubor** - upravte cestu v souboru.

### Krok 4: Nastavení proměnných prostředí (volitelné)
V PythonAnywhere dashboardu → Web → Environment variables:
- `SECRET_KEY` = `váš-tajný-klíč-min-32-znaků`
- `DATABASE_URL` = `sqlite:///odbery.db` (nebo cesta k vaší databázi)

**Důležité:** Pokud nenastavíte `SECRET_KEY`, aplikace použije defaultní hodnotu (změňte ji v produkci!)

### Krok 5: Nastavení statických souborů
V PythonAnywhere dashboardu → Web → Static files:
- URL: `/static/`
- Directory: `/home/yourusername/odberos/site/static/`

### Krok 6: Reload aplikace
Klikněte na tlačítko "Reload" v PythonAnywhere dashboardu.

## 🔧 Kontrola po nasazení

### 1. Test základních funkcí
- [ ] Hlavní stránka se načte
- [ ] Přihlášení funguje (PIN: 0000 pro admin)
- [ ] Odběry se zobrazují
- [ ] Reklamace se zobrazují
- [ ] Admin dashboard funguje
- [ ] Statistiky se načítají

### 2. Test databáze
- [ ] Databáze se vytvoří automaticky při prvním spuštění
- [ ] Migrace proběhne automaticky
- [ ] Defaultní admin se vytvoří (username: `admin`, PIN: `0000`, password: `admin123`)

### 3. Test exportu
- [ ] CSV export funguje
- [ ] Excel export funguje (pokud je nainstalován openpyxl)

## ⚠️ Důležité poznámky

### Bezpečnost
1. **Změňte defaultní SECRET_KEY** v produkci!
   - Vytvořte silný náhodný klíč (min. 32 znaků)
   - Nastavte ho jako environment variable na PythonAnywhere

2. **Změňte defaultní admin PIN a heslo** po prvním přihlášení!

3. **Zkontrolujte oprávnění** - ujistěte se, že pouze oprávnění uživatelé mají přístup

### Databáze
- SQLite databáze se vytvoří v adresáři `instance/`
- Pro větší projekty zvažte přechod na PostgreSQL nebo MySQL
- Pravidelně zálohujte databázi!

### Logy
- Logy Flask aplikace najdete v PythonAnywhere dashboardu → Web → Error log
- Pro debugging použijte `app.logger.error()` v kódu

## 🐛 Řešení problémů

### Aplikace se nenačte
1. Zkontrolujte error log v PythonAnywhere dashboardu
2. Ověřte, že všechny závislosti jsou nainstalované
3. Zkontrolujte cestu v WSGI konfiguraci

### Databáze nefunguje
1. Zkontrolujte oprávnění k adresáři `instance/`
2. Ověřte, že migrace proběhla (zkontrolujte sloupce v databázi)
3. Zkontrolujte error logy

### Statické soubory se nenačítají
1. Zkontrolujte konfiguraci statických souborů v dashboardu
2. Ověřte, že cesty jsou správné

## 📞 Podpora

Pokud narazíte na problémy:
1. Zkontrolujte error logy v PythonAnywhere dashboardu
2. Ověřte, že všechny závislosti jsou nainstalované
3. Zkontrolujte konfiguraci WSGI a statických souborů

---

**Aplikace je připravena na nasazení! 🎉**
