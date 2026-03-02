# Fly.io – Odběry a reklamace
FROM python:3.12-slim

WORKDIR /app

# Systémové závislosti (pro SQLite, openpyxl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Kopírování a instalace Python závislostí
COPY site/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikace
COPY site/ .

# Adresář pro data (SQLite) – volume se připojí v fly.toml
RUN mkdir -p /data

ENV PORT=8080
EXPOSE 8080

# Waitress – produkční WSGI server
CMD ["python", "run_waitress.py"]
