"""Produkty - seznam, detail, editace, export."""
import csv
from decimal import Decimal
from io import StringIO, BytesIO

from flask import Blueprint, flash, g, redirect, render_template, request, url_for, Response
from flask_login import login_required, current_user

from app.models import Product
from app.utils.normalizer import product_key_normalized
from app.utils.loaders import get_product_or_404
from app.services.audit_service import log as audit_log

products_bp = Blueprint("products", __name__)


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


def _parse_override(value):
    if not value or not str(value).strip():
        return None
    try:
        d = Decimal(str(value).strip().replace(",", "."))
        return d.quantize(Decimal("0.01"))  # 2 desetinná místa
    except Exception:
        return None


@products_bp.route("/search")
@login_required
def search():
    """Fragment pro HTMX: vyhledá produkty podle q, vrátí HTML seznam (max 25)."""
    from sqlalchemy import or_
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return "<p class=\"text-muted small mb-0\">Napište alespoň 2 znaky pro vyhledání.</p>"
    q_like = f"%{q}%"
    query = g.db.query(Product).filter(Product.active == True).filter(
        or_(
            Product.description.ilike(q_like),
            (Product.description2.isnot(None) & Product.description2.ilike(q_like)),
            (Product.pot_size.isnot(None) & Product.pot_size.ilike(q_like)),
            (Product.ean_code.isnot(None) & Product.ean_code.ilike(q_like)),
            (Product.vbn_code.isnot(None) & Product.vbn_code.ilike(q_like)),
        )
    )
    products = query.order_by(Product.description).limit(25).all()
    return render_template("products/search_fragment.html", products=products, q=q)


PER_PAGE_PRODUCTS = 50


def _product_list_base_query(g_db, q, pot_size, active):
    """Základní dotaz s filtrem (bez limit/offset)."""
    from sqlalchemy import or_
    query = g_db.query(Product)
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                Product.description.ilike(q_like),
                (Product.description2.isnot(None) & Product.description2.ilike(q_like)),
                (Product.pot_size.isnot(None) & Product.pot_size.ilike(q_like)),
                (Product.ean_code.isnot(None) & Product.ean_code.ilike(q_like)),
                (Product.vbn_code.isnot(None) & Product.vbn_code.ilike(q_like)),
            )
        )
    if pot_size:
        query = query.filter(Product.pot_size == pot_size)
    if active == "1":
        query = query.filter(Product.active == True)
    elif active == "0":
        query = query.filter(Product.active == False)
    return query.order_by(Product.description)


@products_bp.route("")
@login_required
def product_list():
    q = (request.args.get("q") or "").strip()
    pot_size = request.args.get("pot_size", "")
    active = request.args.get("active", "")
    page = max(1, int(request.args.get("page", 1)))
    base = _product_list_base_query(g.db, q, pot_size, active)
    total = base.count()
    total_pages = max(1, (total + PER_PAGE_PRODUCTS - 1) // PER_PAGE_PRODUCTS)
    page = min(page, total_pages)
    products = base.offset((page - 1) * PER_PAGE_PRODUCTS).limit(PER_PAGE_PRODUCTS).all()
    pot_sizes = [r[0] for r in g.db.query(Product.pot_size).distinct().filter(Product.pot_size.isnot(None)).order_by(Product.pot_size).all()]
    ctx = {
        **_ctx(),
        "products": products,
        "q": q,
        "pot_size": pot_size,
        "active_filter": active,
        "pot_sizes": pot_sizes,
        "page": page,
        "per_page": PER_PAGE_PRODUCTS,
        "total": total,
        "total_pages": total_pages,
    }
    if request.headers.get("HX-Request"):
        return render_template("products/list_rows.html", **ctx)
    return render_template("products/list.html", **ctx)


@products_bp.route("/export")
@login_required
def export_list():
    """Export produktů podle aktuálních filtrů – CSV nebo XLSX."""
    q = (request.args.get("q") or "").strip()
    pot_size = request.args.get("pot_size", "")
    active = request.args.get("active", "")
    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt not in ("csv", "xlsx"):
        fmt = "csv"
    base = _product_list_base_query(g.db, q, pot_size, active)
    products = base.limit(10000).all()  # export: max 10k řádků
    if fmt == "csv":
        buf = StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow([
            "ID", "Description", "Description 2", "Pot-Size", "EAN", "VBN", "Aktivní",
            "Prodejní cena", "Nákupní cena", "VIP CZK", "Obchod (D1)", "D4",
        ])
        for p in products:
            w.writerow([
                p.id,
                (p.description or ""),
                (p.description2 or ""),
                (p.pot_size or ""),
                (p.ean_code or ""),
                (p.vbn_code or ""),
                "Ano" if p.active else "Ne",
                str(p.effective_sales_price() or ""),
                str(p.effective_purchase_price() or ""),
                str(p.effective_vip_czk() or ""),
                str(p.effective_trade_price() or ""),
                str(p.effective_d4_price() or ""),
            ])
        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=produkty.csv"},
        )
    # xlsx
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Produkty"
    headers = [
        "ID", "Description", "Description 2", "Pot-Size", "EAN", "VBN", "Aktivní",
        "Prodejní cena", "Nákupní cena", "VIP CZK", "Obchod (D1)", "D4",
    ]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for p in products:
        ws.append([
            p.id,
            (p.description or ""),
            (p.description2 or ""),
            (p.pot_size or ""),
            (p.ean_code or ""),
            (p.vbn_code or ""),
            "Ano" if p.active else "Ne",
            float(p.effective_sales_price()) if p.effective_sales_price() is not None else None,
            float(p.effective_purchase_price()) if p.effective_purchase_price() is not None else None,
            float(p.effective_vip_czk()) if p.effective_vip_czk() is not None else None,
            float(p.effective_trade_price()) if p.effective_trade_price() is not None else None,
            float(p.effective_d4_price()) if p.effective_d4_price() is not None else None,
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=produkty.xlsx"},
    )


@products_bp.route("/<int:product_id>", methods=["GET", "POST"])
@login_required
def detail(product_id):
    product = get_product_or_404(g.db, product_id)
    if request.method == "POST":
        product.description = request.form.get("description", "").strip()
        product.description2 = (request.form.get("description2") or "").strip() or None
        product.pot_size = (request.form.get("pot_size") or "").strip() or None
        product.product_key_normalized = product_key_normalized(product.description, product.pot_size)
        product.active = request.form.get("active") == "1"
        product.sales_price_override = _parse_override(request.form.get("sales_price_override"))
        product.purchase_price_override = _parse_override(request.form.get("purchase_price_override"))
        product.margin_7_override = _parse_override(request.form.get("margin_7_override"))
        product.vip_eur_override = _parse_override(request.form.get("vip_eur_override"))
        product.vip_czk_override = _parse_override(request.form.get("vip_czk_override"))
        product.trade_price_override = _parse_override(request.form.get("trade_price_override"))
        product.d4_price_override = _parse_override(request.form.get("d4_price_override"))
        audit_log(g.db, "product", product.id, getattr(current_user, "id", None), "update", "Změna údajů produktu")
        g.db.commit()
        flash("Změny u produktu byly uloženy.", "success")
        return redirect(url_for("products.detail", product_id=product_id))
    return render_template("products/detail.html", **_ctx(), product=product)
