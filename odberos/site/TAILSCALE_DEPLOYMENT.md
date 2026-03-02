# Nasazení na vlastní server přes Tailscale

Aplikace **Odběry** běží na vašem serveru a je dostupná jen v rámci Tailscale sítě (ne z internetu).

---

## Co potřebujete

- **Server** (Linux) s nainstalovaným [Tailscale](https://tailscale.com/download)
- **Python 3.10+** (nebo Docker)
- Na počítačích, ze kterých budete přistupovat, musí být taky Tailscale (stejný účet / síť)

---

## 1. Připravit server

### Tailscale na serveru

```bash
# Ubuntu/Debian
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Zjistěte Tailscale IP serveru (např. 100.x.x.x)
tailscale ip -4
```

### Python a aplikace

```bash
# Složka pro aplikaci (změňte podle sebe)
sudo mkdir -p /opt/odberos
sudo chown "$USER" /opt/odberos

# Nahrajte obsah repozitáře do /opt/odberos (git clone nebo rsync/scp)
# Očekávaná struktura:
# /opt/odberos/
#   site/
#     app.py
#     run_waitress.py
#     requirements.txt
#     templates/
#     static/
#     ...
```

---

## 2. Konfigurace prostředí

V adresáři `site/` vytvořte soubor `.env` (nebo nastavte proměnné v systemd / docker):

```bash
cd /opt/odberos/site

# Vygenerujte SECRET_KEY (min. 32 znaků)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Vytvořte .env (volitelné – nebo viz systemd níže)
cat << 'EOF' > .env
SECRET_KEY=vygenerovaný-klíč-sem
FLASK_ENV=production
# Přístup jen přes HTTP (Tailscale): session cookies musí jít po HTTP
ALLOW_HTTP_SESSION=1
DATABASE_URL=sqlite:///odbery.db
PORT=8080
EOF
```

**Důležité:**  
- Při **pouze HTTP** (např. `http://100.x.x.x:8080`) bez HTTPS nastavte `ALLOW_HTTP_SESSION=1`, aby session cookies fungovaly. Můžete nechat `FLASK_ENV=production`.  
- Pokud před aplikací máte **HTTPS** (Caddy/nginx), `ALLOW_HTTP_SESSION` nepotřebujete.

---

## 3. Spuštění aplikace

### Varianta A: Přímo na serveru (venv + Waitress)

```bash
cd /opt/odberos/site
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Načtení .env (pokud máte python-dotenv)
# pip install python-dotenv
# V app.py lze přidat na začátek: from dotenv import load_dotenv; load_dotenv()

export SECRET_KEY="váš-vygenerovaný-klíč"
export FLASK_ENV=production
export PORT=8080
python run_waitress.py
```

Aplikace naslouchá na `0.0.0.0:8080`, tedy i na Tailscale IP.

### Varianta B: Systemd (automatický start po startu serveru)

1. Vytvořte env soubor **na serveru** v `/opt/odberos/site/odberos.env` (systemd načte `odberos.env`, ne `.env`).  
   **Pokud tam soubor není nebo je prázdný**, přihlaste se na server (SSH) a spusťte:

Nejdřív zjistěte, kde aplikace na serveru leží (měla by tam být složka `site` s `app.py`, `run_waitress.py`):

```bash
# Kde je aplikace? (typicky /opt/odberos nebo /home/xxx/odberos)
ls -la /opt/odberos/site 2>/dev/null || ls -la ~/odberos/site 2>/dev/null || find /opt /home -name "run_waitress.py" 2>/dev/null | head -5
```

Pak vytvořte `odberos.env` (SITE_DIR nahraďte skutečnou cestou, např. `/opt/odberos/site` nebo `/home/vase_jmeno/odberos/site`):

```bash
# Vygenerovat klíč a vytvořit soubor (cestu upravte)
SITE_DIR=/opt/odberos/site
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sudo bash -c "printf 'SECRET_KEY=%s\nFLASK_ENV=production\nALLOW_HTTP_SESSION=1\nPORT=8080\n' '$KEY' > $SITE_DIR/odberos.env && chmod 600 $SITE_DIR/odberos.env"
```

Nemáte-li sudo, vytvořte soubor tam, kde máte práva, a pak ho zkopírujte. **Pokud adresář neexistuje**, nejdřív ho vytvořte:

```bash
# 1) Vytvořit adresář (pokud chcete používat /opt/odberos/site)
sudo mkdir -p /opt/odberos/site
sudo chown "$USER" /opt/odberos/site   # aby vám patřil, nebo nechte root a použijte sudo níže

# 2) Vytvořit odberos.env (s sudo pokud adresář patří root)
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
printf 'SECRET_KEY=%s\nFLASK_ENV=production\nALLOW_HTTP_SESSION=1\nPORT=8080\n' "$KEY" | sudo tee /opt/odberos/site/odberos.env > /dev/null
sudo chmod 600 /opt/odberos/site/odberos.env
```

**Aplikace je jinde** (např. v `/home/xxx/odberos/site`)? Pak vytvořte soubor tam a v `odberos.service` změňte cestu na vaši:
```bash
# Příklad: aplikace v /home/jmeno/odberos/site
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
printf 'SECRET_KEY=%s\nFLASK_ENV=production\nALLOW_HTTP_SESSION=1\nPORT=8080\n' "$KEY" > /home/jmeno/odberos/site/odberos.env
chmod 600 /home/jmeno/odberos/site/odberos.env
```

Kontrola (soubor vlastní root → použijte `sudo cat`): `sudo cat /opt/odberos/site/odberos.env`. Pak restart: `sudo systemctl restart odberos`.

2. Volitelně vytvořte uživatele `odberos` (nebo v unit souboru změňte `User=` na své jméno):

```bash
sudo useradd -r -s /bin/false odberos
sudo chown -R odberos:odberos /opt/odberos
```

3. Nainstalujte a spusťte službu:

```bash
sudo cp /opt/odberos/site/odberos.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable odberos
sudo systemctl start odberos
sudo systemctl status odberos
```

Logy: `journalctl -u odberos -f`

### Varianta C: Docker

V kořeni projektu (`/opt/odberos`) vytvořte `.env` s `SECRET_KEY` a spusťte:

```bash
cd /opt/odberos
echo "SECRET_KEY=vygenerovaný-klíč" >> .env
echo "ALLOW_HTTP_SESSION=1" >> .env
docker compose up -d
```

Databáze se ukládá do Docker volume `odberos_data` (přežije restart).

---

## 4. Přístup k aplikaci

- Na serveru zjistíte Tailscale IP: `tailscale ip -4` (např. `100.64.1.2`).
- Na jakémkoli zařízení v téže Tailscale síti otevřete v prohlížeči:
  - **http://100.64.1.2:8080** (nahraďte IP vaší)
- První přihlášení: uživatel `admin`, PIN `0000`, heslo `admin123` – **ihned po přihlášení změňte**.

---

## 5. Řešení problémů

### Lokálně to jde, na serveru formulář „nepustí“ (přidat odběr / reklamaci)

**Příčina:** Přes Tailscale používáte **HTTP** (`http://100.x.x.x:8080`). V produkci má aplikace **Secure** session cookie – prohlížeč ji pošle jen přes HTTPS. Na HTTP se tedy session neposílá, po odeslání formuláře vás to „odhlásí“ nebo stránka nepřijme odeslání.

**Řešení:** Na serveru nastavte **`ALLOW_HTTP_SESSION=1`** (povolí session přes HTTP).

- **Systemd:** Potřebujete soubor `/opt/odberos/site/odberos.env`. Pokud tam nic není, vytvořte ho (viz krok 1 u Varianty B výše). V něm musí být řádek `ALLOW_HTTP_SESSION=1`. Pak:
  ```bash
  sudo systemctl restart odberos
  ```
- **Ruční spuštění:** před `python run_waitress.py`:
  ```bash
  export ALLOW_HTTP_SESSION=1
  ```
- **Docker:** V `.env` v kořeni projektu přidejte `ALLOW_HTTP_SESSION=1` a `docker compose up -d` znovu spusťte.

Po změně **restartujte aplikaci** a v prohlížeči zkuste znovu (příp. tvrdé obnovení stránky Ctrl+Shift+R).

---

## 6. Bezpečnost

- Aplikace je dostupná **jen v Tailscale síti**, ne na veřejném internetu (pokud neotevřete port jinak).
- **SECRET_KEY** vždy nastavte z prostředí (ne výchozí z kódu).
- Po prvním přihlášení **změňte admin PIN a heslo**.
- Doporučeno: **pravidelná záloha** `site/odbery.db` (např. cron).

---

## 7. Záloha databáze

```bash
# Jednoduchý cron (denně ve 2:00)
0 2 * * * cp /opt/odberos/site/odbery.db /opt/odberos/backups/odbery_$(date +\%Y\%m\%d).db
```

---

## 8. Aktualizace aplikace

```bash
cd /opt/odberos
git pull   # nebo nahrajte nové soubory
cd site
# Pokud používáte venv:
source .venv/bin/activate
pip install -r requirements.txt
# Restart
sudo systemctl restart odberos   # při systemd
# nebo docker compose up -d --build   # při Dockeru
```

---

**Shrnutí:** Server s Tailscale → nainstalovat Python/Docker → nastavit SECRET_KEY a FLASK_ENV → spustit Waitress (ručně/systemd/Docker) → přístup na `http://<tailscale-ip>:8080`.
