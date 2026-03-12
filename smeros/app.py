import os
try:
    import requests
except ImportError:
    requests = None

from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-in-production-smeros")
# Session jen do zavření prohlížeče (nastavíme session.permanent = False)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "smeros_session"
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

AUTH_API_URL = (os.environ.get("AUTH_API_URL") or "http://localhost:8080").rstrip("/")
# Stejná hodnota musí být v auth-system (config.SSO_SECRET), jinak SSO nefunguje
SSO_SECRET = (os.environ.get("SSO_SECRET") or "sso-dev-secret").strip()


@app.context_processor
def inject_theme_viktorinka():
    user = session.get("smeros_user") or {}
    theme_viktorinka = (user.get("username") or "").strip().lower() == "viktorinka"
    return {"theme_viktorinka": theme_viktorinka}


apps_all = [
    {"name": "Odběros", "port": 8081, "code": "odberos", "description": "Systém pro odběry a PPL", "icon": "📦"},
    {"name": "Objednávač", "port": 8082, "code": "objednavac", "description": "Interní objednávkový systém", "icon": "🧾"},
    {"name": "DPD - počítač", "port": 8083, "code": "dpd", "description": "Systém pro vyplácení DPD dobírek", "icon": "🚚"},
    {"name": "Správa uživatelů", "port": 8080, "code": "auth", "description": "Centrální databáze uživatelů – přihlášení do všech aplikací", "icon": "👤"},
]


@app.route("/")
def index():
    user = session.get("smeros_user")
    if not user:
        return redirect(url_for("login"))
    allowed = session.get("allowed_apps") or []
    allowed_lower = {str(x).strip().lower() for x in allowed if x}
    if user.get("role") == "admin":
        apps = apps_all
    else:
        apps = [a for a in apps_all if (a.get("code") or "").lower() in allowed_lower]
    return render_template("index.html", apps=apps, user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("smeros_user"):
        return redirect(url_for("index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        if not username or not pin:
            flash("Zadejte uživatelské jméno a PIN.", "error")
            return render_template("login.html")
        if not requests:
            flash("Chyba serveru: modul requests není k dispozici.", "error")
            return render_template("login.html")
        try:
            r = requests.post(
                AUTH_API_URL + "/api/login",
                json={"username": username, "pin": pin, "application": "smeros"},
                timeout=10,
            )
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code == 200 and data.get("ok"):
                session["smeros_user"] = {"username": data["username"], "role": data.get("role", "user")}
                session["allowed_apps"] = data.get("allowed_apps") or []
                flash("Přihlášení proběhlo.", "success")
                next_url = request.args.get("next", "").strip()
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("index"))
            flash(data.get("error", "Neplatné přihlašovací údaje."), "error")
        except Exception as e:
            flash(f"Nepodařilo se spojit s přihlášením: {e}", "error")
        return render_template("login.html")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("smeros_user", None)
    session.pop("allowed_apps", None)
    # Řetěz bez vnořeného next: auth → Odběros → Objednávač → DPD → login (každá app jen jedna URL)
    flash("Byli jste odhlášeni ze všech aplikací.", "info")
    return redirect(AUTH_API_URL + "/admin/logout")


@app.route("/open/<int:port>")
def open_app(port):
    """Přesměruje na podaplikaci s SSO tokenem (pokud je uživatel přihlášen)."""
    user = session.get("smeros_user")
    if not user:
        flash("Pro otevření aplikace se nejdřív přihlaste.", "info")
        return redirect(url_for("login", next=url_for("open_app", port=port)))
    allowed_ports = {a["port"] for a in apps_all}
    if port not in allowed_ports:
        flash("Neplatná aplikace.", "error")
        return redirect(url_for("index"))
    if user.get("role") != "admin":
        app_for_port = next((a for a in apps_all if a["port"] == port), None)
        allowed_raw = session.get("allowed_apps") or []
        allowed_lower = {str(x).strip().lower() for x in allowed_raw if x}
        if app_for_port and (app_for_port.get("code") or "").lower() not in allowed_lower:
            flash("Nemáte přístup k této aplikaci.", "error")
            return redirect(url_for("index"))
    if not requests:
        flash("SSO vyžaduje modul requests (pip install requests).", "error")
        host = request.host.split(":")[0]
        return redirect(f"http://{host}:{port}")
    try:
        r = requests.post(
            AUTH_API_URL + "/api/sso/create-token",
            json={"username": user["username"]},
            headers={"X-SSO-Secret": SSO_SECRET},
            timeout=5,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or not data.get("ok"):
            flash("SSO token se nepodařilo vytvořit – zkontrolujte, že auth-system běží a SSO_SECRET je stejný.", "error")
            host = request.host.split(":")[0]
            return redirect(f"http://{host}:{port}")
        token = data.get("token", "")
        if not token:
            flash("SSO: prázdný token.", "error")
            host = request.host.split(":")[0]
            return redirect(f"http://{host}:{port}")
        host = request.host.split(":")[0]
        return redirect(f"http://{host}:{port}/auth/sso?token={token}")
    except Exception as e:
        flash(f"SSO chyba: {e}. Zkontrolujte AUTH_API_URL a že auth-system běží.", "error")
        host = request.host.split(":")[0]
        return redirect(f"http://{host}:{port}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
