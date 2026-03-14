# Nasazení do produkce

## 1. Proměnné prostředí

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export FLASK_DEBUG=0
```

**E-mail notifikace** (volitelné):
```bash
export MAIL_FROM=smenovac@domena.cz
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USER=user
export SMTP_PASS=heslo
```

**Gmail** (2FA + App heslo nutné):
```bash
export MAIL_FROM=vas@gmail.com
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=vas@gmail.com
export SMTP_PASS=xxxx-xxxx-xxxx-xxxx   # App heslo z účtu Google
```

## 2. Spuštění s Gunicornem

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run_production:app
```

## 3. Nginx (před Gunicorn)

```nginx
server {
    listen 80;
    server_name vase-domena.cz;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Pak SSL přes Let's Encrypt (certbot).

## 4. SQLite vs PostgreSQL

- SQLite: vhodné pro malý tým (~do 10 uživatelů). DB soubor `smeny.db` zálohujte.
- PostgreSQL: pro větší nasazení nastavte `DATABASE_URL=postgresql://...`
