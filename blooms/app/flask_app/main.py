"""Úvodní stránka a dashboard."""
from pathlib import Path

from flask import Blueprint, current_app, g, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app.models import Product, Customer, DeliveryNote, ImportBatch
from app.services.stats_service import (
    top_customers_by_revenue,
    top_products_by_quantity,
    delivery_notes_by_month,
)

main_bp = Blueprint("main", __name__)


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
