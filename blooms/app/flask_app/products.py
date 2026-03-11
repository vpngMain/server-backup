"""Produkty - seznam, detail, editace, export."""
import csv
import json
from decimal import Decimal
from io import StringIO, BytesIO
from difflib import SequenceMatcher

from flask import Blueprint, flash, g, redirect, render_template, request, url_for, Response, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app.models import Product, DeliveryNoteItem, DeliveryNote
from app.utils.normalizer import product_key_normalized, base_description_for_key
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
        return d.quantize(Decimal("0.0001"))  # 4 desetinná místa
    except Exception:
        return None


@products_bp.route("/search")
@login_required
def search():
    """Fragment pro HTMX: vyhledá produkty podle q, vrátí HTML seznam (max 25)."""
    from sqlalchemy import or_
    q = (request.args.get("q") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
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
    candidates = query.order_by(Product.description).limit(120).all()
    if not candidates:
        # Fallback pro fuzzy i při slabé shodě
        candidates = g.db.query(Product).filter(Product.active == True).order_by(Product.description).limit(120).all()

    usage_map: dict[int, dict] = {}
    customer_id_int = None
    try:
        customer_id_int = int(customer_id) if customer_id else None
    except Exception:
        customer_id_int = None
    if customer_id_int:
        usage_rows = (
            g.db.query(
                DeliveryNoteItem.product_id,
                func.count(DeliveryNoteItem.id),
                func.max(DeliveryNote.issue_date),
            )
            .join(DeliveryNote, DeliveryNote.id == DeliveryNoteItem.delivery_note_id)
            .filter(
                DeliveryNote.customer_id == customer_id_int,
                DeliveryNoteItem.product_id.isnot(None),
            )
            .group_by(DeliveryNoteItem.product_id)
            .all()
        )
        for pid, cnt, last_dt in usage_rows:
            if not pid:
                continue
            usage_map[int(pid)] = {
                "count": int(cnt or 0),
                "last_date": str(last_dt or ""),
            }

    q_low = q.casefold()

    def _score(p: Product) -> float:
        text = " ".join([
            p.description or "",
            p.description2 or "",
            p.pot_size or "",
            p.ean_code or "",
            p.vbn_code or "",
        ]).casefold()
        score = 0.0
        desc = (p.description or "").casefold()
        if desc.startswith(q_low):
            score += 35
        if q_low in desc:
            score += 20
        if q_low in text:
            score += 12
        score += SequenceMatcher(None, q_low, text[:120]).ratio() * 40
        use = usage_map.get(int(p.id), {})
        if use:
            score += min(use.get("count", 0), 12) * 2.5
            if use.get("last_date"):
                score += 6
        return score

    ranked = sorted(candidates, key=_score, reverse=True)[:25]
    return render_template("products/search_fragment.html", products=ranked, q=q, usage_map=usage_map)


PER_PAGE_PRODUCTS = 50
PRODUCT_LIST_COLUMNS: list[tuple[str, str]] = [
    ("description", "Description"),
    ("description2", "Description 2"),
    ("pot_size", "Pot-Size"),
    ("ean_code", "EAN"),
    ("vbn_code", "VBN"),
    ("sales_price", "Sales Price"),
    ("purchase_price", "Cena + doprava"),
    ("vip_czk", "VIP CZK"),
    ("trade_price", "D1 (obchod)"),
    ("d4_price", "D4"),
]
PRODUCT_LIST_COLUMN_KEYS = {k for k, _ in PRODUCT_LIST_COLUMNS}
DEFAULT_PRODUCT_LIST_COLUMNS = ["description", "description2", "pot_size"]


def _sanitize_product_columns(cols) -> list[str]:
    cleaned = [c for c in cols if c in PRODUCT_LIST_COLUMN_KEYS]
    if "description" not in cleaned:
        cleaned.insert(0, "description")
    # zachovat pořadí dle PRODUCT_LIST_COLUMNS
    ordered = [k for k, _ in PRODUCT_LIST_COLUMNS if k in cleaned]
    return ordered or DEFAULT_PRODUCT_LIST_COLUMNS


def _product_list_base_query(g_db, q, pot_size):
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
    return query.order_by(Product.description)


@products_bp.route("")
@login_required
def product_list():
    q = (request.args.get("q") or "").strip()
    pot_size = request.args.get("pot_size", "")
    page = max(1, int(request.args.get("page", 1)))
    selected_columns: list[str]
    has_columns_param = "columns" in request.args
    if has_columns_param:
        selected_columns = _sanitize_product_columns(request.args.getlist("columns"))
    else:
        selected_columns = []
        raw = getattr(current_user, "products_columns_json", None)
        if raw:
            try:
                selected_columns = _sanitize_product_columns(json.loads(raw))
            except Exception:
                selected_columns = []
        if not selected_columns:
            selected_columns = DEFAULT_PRODUCT_LIST_COLUMNS

    # Ulož preference sloupců k uživateli (per účet)
    new_pref_json = json.dumps(selected_columns, ensure_ascii=False)
    if getattr(current_user, "products_columns_json", None) != new_pref_json:
        current_user.products_columns_json = new_pref_json
        g.db.commit()

    base = _product_list_base_query(g.db, q, pot_size)
    total = base.count()
    total_pages = max(1, (total + PER_PAGE_PRODUCTS - 1) // PER_PAGE_PRODUCTS)
    page = min(page, total_pages)
    products = base.offset((page - 1) * PER_PAGE_PRODUCTS).limit(PER_PAGE_PRODUCTS).all()
    pot_sizes = [r[0] for r in g.db.query(Product.pot_size).distinct().filter(Product.pot_size.isnot(None)).order_by(Product.pot_size).all()]
    use_tabulator = bool(current_app.config.get("USE_TABULATOR", True))
    products_rows_compact = []
    if use_tabulator:
        for p in products:
            products_rows_compact.append({
                "id": p.id,
                "description": p.description or "",
                "description2": p.description2 or "",
                "pot_size": p.pot_size or "",
                "ean_code": p.ean_code or "",
                "vbn_code": p.vbn_code or "",
                "sales_price": str(p.effective_sales_price() or ""),
                "purchase_price": str(p.effective_purchase_price() or ""),
                "vip_czk": str(p.effective_vip_czk() or ""),
                "trade_price": str(p.effective_trade_price() or ""),
                "d4_price": str(p.effective_d4_price() or ""),
                "detail_url": url_for("products.detail", product_id=p.id),
            })
    ctx = {
        **_ctx(),
        "products": products,
        "q": q,
        "pot_size": pot_size,
        "pot_sizes": pot_sizes,
        "page": page,
        "per_page": PER_PAGE_PRODUCTS,
        "total": total,
        "total_pages": total_pages,
        "selected_columns": selected_columns,
        "available_columns": PRODUCT_LIST_COLUMNS,
        "use_tabulator": use_tabulator,
        "products_rows_compact": products_rows_compact,
    }
    if request.headers.get("HX-Request"):
        return render_template("products/table.html", **ctx)
    return render_template("products/list.html", **ctx)


@products_bp.route("/export")
@login_required
def export_list():
    """Export produktů podle aktuálních filtrů – CSV nebo XLSX."""
    q = (request.args.get("q") or "").strip()
    pot_size = request.args.get("pot_size", "")
    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt not in ("csv", "xlsx"):
        fmt = "csv"
    base = _product_list_base_query(g.db, q, pot_size)
    products = base.limit(10000).all()  # export: max 10k řádků
    if fmt == "csv":
        buf = StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow([
            "ID", "Description", "Description 2", "Pot-Size", "EAN", "VBN",
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
        "ID", "Description", "Description 2", "Pot-Size", "EAN", "VBN",
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
        product.product_key_normalized = product_key_normalized(
            base_description_for_key(product.description, product.pot_size),
            product.pot_size,
        )
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
