"""Úvodní stránka a dashboard."""
import json
from pathlib import Path

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app.config import BASE_DIR
from app.models import Product, Customer, DeliveryNote, ImportBatch
from app.services.company_profile_service import load_company_profile, save_company_profile, fetch_company_from_ares
from app.services.stats_service import (
    top_customers_by_revenue,
    top_products_by_quantity,
    delivery_notes_by_month,
)

main_bp = Blueprint("main", __name__)


def _require_admin():
    if not current_user.is_authenticated or getattr(current_user, "role", "") != "admin":
        return False
    return True


@main_bp.route("/manifest.webmanifest")
def manifest():
    """PWA manifest – správný Content-Type."""
    static_dir = Path(current_app.static_folder) if current_app.static_folder else None
    if not static_dir or not (static_dir / "manifest.webmanifest").exists():
        return "", 404
    return send_from_directory(
        str(static_dir),
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


@main_bp.route("/sw.js")
def service_worker():
    """Service Worker na root scope (nutné pro cache celé app)."""
    static_dir = Path(current_app.static_folder) if current_app.static_folder else None
    if not static_dir or not (static_dir / "sw.js").exists():
        return "", 404
    return send_from_directory(
        str(static_dir),
        "sw.js",
        mimetype="application/javascript",
    )


@main_bp.route("/offline.html")
def offline_page():
    """Offline fallback stránka pro PWA."""
    static_dir = Path(current_app.static_folder) if current_app.static_folder else None
    if not static_dir or not (static_dir / "offline.html").exists():
        return "", 404
    return send_from_directory(str(static_dir), "offline.html")


@main_bp.route("/vendor/tabulator/<path:filename>")
def tabulator_asset(filename: str):
    """Lokální statické soubory Tabulatoru ze složky /tabulator/dist."""
    dist_dir = BASE_DIR / "tabulator" / "dist"
    if not dist_dir.exists():
        return "", 404
    return send_from_directory(str(dist_dir), filename)


@main_bp.route("/ui/tabulator-state/<string:page_key>", methods=["GET", "POST"])
@login_required
def tabulator_state(page_key: str):
    """Per-uživatel uložený stav gridu (filtry/sort/sloupce) pro Tabulator."""
    raw = getattr(current_user, "tabulator_state_json", None)
    try:
        state_map = json.loads(raw) if raw else {}
        if not isinstance(state_map, dict):
            state_map = {}
    except Exception:
        state_map = {}

    if request.method == "GET":
        return jsonify({"ok": True, "state": state_map.get(page_key)})

    payload = request.get_json(silent=True) or {}
    state = payload.get("state")
    if state is None:
        state_map.pop(page_key, None)
    else:
        state_map[page_key] = state
    current_user.tabulator_state_json = json.dumps(state_map, ensure_ascii=False)
    g.db.commit()
    return jsonify({"ok": True})


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    product_count = g.db.query(Product).count()
    customer_count = g.db.query(Customer).count()
    delivery_count = g.db.query(DeliveryNote).count()
    last_import = g.db.query(ImportBatch).order_by(ImportBatch.imported_at.desc()).first()
    stats_top_customers = top_customers_by_revenue(g.db, limit=8)
    stats_top_products = top_products_by_quantity(g.db, limit=10)
    stats_by_month = delivery_notes_by_month(g.db, months=12)
    return render_template(
        "dashboard.html",
        request=request,
        current_user=current_user,
        dev_skip_auth=False,
        product_count=product_count,
        customer_count=customer_count,
        delivery_count=delivery_count,
        last_import=last_import,
        stats_top_customers=stats_top_customers,
        stats_top_products=stats_top_products,
        stats_by_month=stats_by_month,
    )


@main_bp.route("/settings/company", methods=["GET", "POST"])
@login_required
def company_settings():
    profile = load_company_profile(current_app.config)
    if request.method == "POST":
        action = (request.form.get("action") or "save").strip()
        if action == "load_ares":
            ico = (request.form.get("ico") or profile.get("ico") or "").strip()
            try:
                ares_data = fetch_company_from_ares(ico)
                # Nepřepisuj kontakt bez potvrzení, ponech ruční phone/email.
                ares_data["phone"] = profile.get("phone", "")
                ares_data["email"] = profile.get("email", "")
                profile = ares_data
                flash("Údaje z ARES načteny. Zkontrolujte a uložte.", "info")
            except Exception as e:
                flash(f"ARES chyba: {e}", "warning")
        else:
            profile = {
                "name": (request.form.get("name") or "").strip(),
                "street": (request.form.get("street") or "").strip(),
                "city": (request.form.get("city") or "").strip(),
                "zip": (request.form.get("zip") or "").strip(),
                "country": (request.form.get("country") or "").strip(),
                "ico": (request.form.get("ico") or "").strip(),
                "dic": (request.form.get("dic") or "").strip(),
                "phone": (request.form.get("phone") or "").strip(),
                "email": (request.form.get("email") or "").strip(),
            }
            try:
                profile = save_company_profile(current_app.config, profile)
                flash("Firemní údaje byly uloženy.", "success")
            except Exception as e:
                flash(f"Nepodařilo se uložit: {e}", "danger")
    return render_template(
        "settings/company.html",
        request=request,
        current_user=current_user,
        dev_skip_auth=False,
        profile=profile,
    )
