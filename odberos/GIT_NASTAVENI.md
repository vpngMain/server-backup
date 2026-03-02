# Nastavení Git a nahrání na GitHub

## 1. Instalace Git

1. Stáhněte Git: **https://git-scm.com/download/win**
2. Nainstalujte (ponechte výchozí nastavení)
3. **Restartujte terminál** (nebo celý Cursor/VS Code)

## 2. Inicializace repozitáře

Otevřete **PowerShell** nebo **CMD** a spusťte:

```powershell
cd C:\Users\Thu\Downloads\odberos

git init
```

## 3. Přidání souborů a první commit

```powershell
git add .
git commit -m "Prvni verze - odbery a reklamace"
```

## 4. Propojení s GitHubem

1. Na **https://github.com** vytvořte nový repozitář (např. `odb-ry-a-reklamace`)
2. Nepřidávejte README ani .gitignore – repozitář nechte prázdný
3. Zkopírujte URL repozitáře (např. `https://github.com/vaseksenicky-hue/odb-ry-a-reklamace.git`)

## 5. Nahrání na GitHub

```powershell
git remote add origin https://github.com/VASE_UZIVATELSKE_JMENO/VAS_REPO.git
git branch -M main
git push -u origin main
```

> Nahraďte `VASE_UZIVATELSKE_JMENO` a `VAS_REPO` vaším GitHub jménem a názvem repozitáře.

## 6. Struktura repozitáře

Po nahrání by měl repozitář obsahovat:

```
odb-ry-a-reklamace/
├── site/           ← složka s aplikací
│   ├── app.py
│   ├── requirements.txt
│   ├── run_waitress.py
│   ├── templates/
│   └── ...
├── render.yaml
├── Dockerfile
└── ...
```

V Render Dashboard pak nastavte **Root Directory** = `site`.

---

**Poznámka:** Pokud máte repozitář už vytvořený a chcete jen aktualizovat:

```powershell
cd C:\Users\Thu\Downloads\odberos
git add .
git commit -m "Aktualizace"
git push
```
