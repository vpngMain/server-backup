"""Dodaci listy - zakladni routy."""
from datetime import date
from decimal import Decimal
import json

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app.models import DeliveryNote, DeliveryNoteItem, Customer, Product, AuditLog, User
from app.services.delivery_note_service import next_document_number, recalc_delivery_note_totals
from app.services.company_profile_service import load_company_profile
from app.utils.loaders import get_delivery_note_or_404, get_product_or_404
from app.services.audit_service import log as audit_log

delivery_bp = Blueprint("delivery", __name__)


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


def _parse_date(val):
    return date.fromisoformat(val)


def _sorted_items_abc(items):
    """Seřadí položky dodacího listu podle názvu A→Z (bez ohledu na velikost písmen)."""
    return sorted(items, key=lambda i: ((i.item_name or "").casefold(), i.id or 0))


def _parse_decimal_input(raw, default: Decimal | None = None):
    try:
        return Decimal(str(raw).replace(",", "."))
    except Exception:
        return default


def _build_price_suggestions_map(note, items):
    """Vrátí mapu product_id -> {last_customer_price, min_margin_price, recommended_price}."""
    product_ids = sorted({i.product_id for i in items if i.product_id})
    if not product_ids:
        return {}

    product_map = {
        p.id: p for p in g.db.query(Product).filter(Product.id.in_(product_ids)).all()
    }

    last_price_rows = (
        g.db.query(
            DeliveryNoteItem.product_id,
            DeliveryNoteItem.unit_price,
            DeliveryNote.issue_date,
        )
        .join(DeliveryNote, DeliveryNote.id == DeliveryNoteItem.delivery_note_id)
        .filter(
            DeliveryNote.customer_id == note.customer_id,
            DeliveryNoteItem.product_id.in_(product_ids),
            DeliveryNoteItem.delivery_note_id != note.id,
        )
        .order_by(DeliveryNote.issue_date.desc(), DeliveryNoteItem.id.desc())
        .all()
    )
    last_prices: dict[int, Decimal] = {}
    for pid, price, _issue_date in last_price_rows:
        if pid and pid not in last_prices:
            last_prices[pid] = Decimal(str(price))

    level = getattr(note.customer, "price_level", None) if note.customer else None
    out = {}
    for pid in product_ids:
        p = product_map.get(pid)
        if not p:
            continue
        list_price = (p.price_for_level(level) if level else None) or p.effective_sales_price()
        purchase = p.effective_purchase_price()
        min_margin = (purchase * Decimal("1.07")) if purchase is not None else None
        last_customer = last_prices.get(pid)
        recommended = last_customer or list_price or min_margin
        if recommended is not None and min_margin is not None and recommended < min_margin:
            recommended = min_margin
        out[pid] = {
            "last_customer_price": str(last_customer) if last_customer is not None else "",
            "min_margin_price": str(min_margin) if min_margin is not None else "",
            "recommended_price": str(recommended) if recommended is not None else "",
        }
    return out


def _price_audit_rows_for_note(note_id: int):
    item_ids = [
        r[0]
        for r in (
            g.db.query(DeliveryNoteItem.id)
            .filter(DeliveryNoteItem.delivery_note_id == note_id)
            .all()
        )
    ]
    if not item_ids:
        return []
    logs = (
        g.db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "delivery_note_item",
            AuditLog.entity_id.in_(item_ids),
            AuditLog.action.in_(["price_update", "bulk_update", "quick_action"]),
        )
        .order_by(AuditLog.changed_at.desc(), AuditLog.id.desc())
        .limit(40)
        .all()
    )
    user_ids = sorted({l.user_id for l in logs if l.user_id is not None})
    user_map = {}
    if user_ids:
        user_map = {u.id: u.username for u in g.db.query(User).filter(User.id.in_(user_ids)).all()}
    out = []
    for l in logs:
        out.append({
            "changed_at": l.changed_at,
            "user": user_map.get(l.user_id, "system"),
            "action": l.action,
            "details": l.details or "",
            "item_id": l.entity_id,
        })
    return out




PER_PAGE_DELIVERY = 50


@delivery_bp.route("")
@login_required
def list_():
    status = request.args.get("status", "")
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
    q = (request.args.get("q") or "").strip()  # číslo dokladu
    page = max(1, int(request.args.get("page", 1)))
    query = g.db.query(DeliveryNote).order_by(DeliveryNote.issue_date.desc(), DeliveryNote.id.desc())
    if status == "draft":
        query = query.filter(DeliveryNote.status == "draft")
    elif status == "issued":
        query = query.filter(DeliveryNote.status == "issued")
    if date_from:
        try:
            df = date.fromisoformat(date_from)
            query = query.filter(DeliveryNote.issue_date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = date.fromisoformat(date_to)
            query = query.filter(DeliveryNote.issue_date <= dt)
        except ValueError:
            pass
    if customer_id:
        try:
            cid = int(customer_id)
            query = query.filter(DeliveryNote.customer_id == cid)
        except ValueError:
            pass
    if q:
        query = query.filter(DeliveryNote.document_number.ilike(f"%{q}%"))
    total = query.count()
    total_pages = max(1, (total + PER_PAGE_DELIVERY - 1) // PER_PAGE_DELIVERY)
    page = min(page, total_pages)
    notes = query.offset((page - 1) * PER_PAGE_DELIVERY).limit(PER_PAGE_DELIVERY).all()
    customers = g.db.query(Customer).order_by(Customer.company_name).all()
    use_tabulator = bool(current_app.config.get("USE_TABULATOR", True))
    notes_rows_compact = []
    if use_tabulator:
        for n in notes:
            notes_rows_compact.append({
                "id": n.id,
                "document_number": n.document_number or "",
                "customer": (n.customer.company_name if n.customer else "-"),
                "issue_date": str(n.issue_date or ""),
                "delivery_date": str(n.delivery_date or ""),
                "total_amount": str(n.total_amount or ""),
                "status": "Koncept" if n.status == "draft" else "Vystaveno",
                "detail_url": url_for("delivery.detail", note_id=n.id),
                "print_url": url_for("delivery.print_", note_id=n.id),
                "pdf_url": url_for("delivery.pdf", note_id=n.id),
            })
    return render_template(
        "delivery/list.html",
        **_ctx(),
        notes=notes,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        customer_id=customer_id,
        q=q,
        customers=customers,
        page=page,
        per_page=PER_PAGE_DELIVERY,
        total=total,
        total_pages=total_pages,
        use_tabulator=use_tabulator,
        notes_rows_compact=notes_rows_compact,
    )


@delivery_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        try:
            issue_d = _parse_date(request.form.get("issue_date"))
            delivery_d = _parse_date(request.form.get("delivery_date"))
        except (ValueError, TypeError):
            return redirect(url_for("delivery.new", error="invalid_date"))
        customer_id = int(request.form.get("customer_id"))
        note_obj = DeliveryNote(
            document_number=request.form.get("document_number", "").strip(),
            customer_id=customer_id,
            issue_date=issue_d,
            delivery_date=delivery_d,
            note=(request.form.get("note") or "").strip() or None,
            status="draft",
            created_by_user_id=current_user.id,
        )
        g.db.add(note_obj)
        g.db.flush()
        audit_log(g.db, "delivery_note", note_obj.id, getattr(current_user, "id", None), "create", "Vytvoření dodacího listu")
        g.db.commit()
        flash("Dodací list byl vytvořen.", "success")
        return redirect(url_for("delivery.detail", note_id=note_obj.id))
    doc_number = next_document_number(g.db)
    customers = g.db.query(Customer).order_by(Customer.company_name).all()
    err = "Neplatny format data." if request.args.get("error") == "invalid_date" else None
    return render_template(
        "delivery/form.html", **_ctx(), note=None, document_number=doc_number,
        customers=customers, today=date.today().isoformat(), error=err,
    )


@delivery_bp.route("/<int:note_id>", methods=["GET", "POST"])
@login_required
def detail(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    if request.method == "POST":
        try:
            note.issue_date = _parse_date(request.form.get("issue_date"))
            note.delivery_date = _parse_date(request.form.get("delivery_date"))
        except (ValueError, TypeError):
            return redirect(url_for("delivery.detail", note_id=note_id, error="invalid_date"))
        note.document_number = request.form.get("document_number", "").strip()
        note.customer_id = int(request.form.get("customer_id"))
        note.note = (request.form.get("note") or "").strip() or None
        audit_log(g.db, "delivery_note", note_id, getattr(current_user, "id", None), "update", "Úprava údajů dodacího listu")
        g.db.commit()
        flash("Dodací list byl upraven.", "success")
        return redirect(url_for("delivery.detail", note_id=note_id))
    customers = g.db.query(Customer).order_by(Customer.company_name).all()
    err = "Neplatný formát data." if request.args.get("error") == "invalid_date" else None
    use_tabulator = bool(current_app.config.get("USE_TABULATOR", True))
    sorted_items = _sorted_items_abc(note.items)
    suggestions_map = _build_price_suggestions_map(note, sorted_items)
    items_rows_compact = []
    if use_tabulator:
        for item in sorted_items:
            s = suggestions_map.get(item.product_id or 0, {})
            items_rows_compact.append({
                "id": item.id,
                "product_id": item.product_id,
                "item_name": item.item_name or "",
                "item_description": item.item_description or "",
                "quantity": str(item.quantity or ""),
                "unit": item.unit or "ks",
                "unit_price": str(item.unit_price or ""),
                "line_total": str(item.line_total or ""),
                "delete_url": url_for("delivery.item_delete", note_id=note_id, item_id=item.id),
                "update_price_url": url_for("delivery.item_update_price", note_id=note_id, item_id=item.id),
                "quick_action_url": url_for("delivery.item_quick_action", note_id=note_id, item_id=item.id),
                "last_customer_price": s.get("last_customer_price", ""),
                "min_margin_price": s.get("min_margin_price", ""),
                "recommended_price": s.get("recommended_price", ""),
            })
    return render_template(
        "delivery/detail.html",
        **_ctx(),
        note=note,
        customers=customers,
        error=err,
        sorted_items=sorted_items,
        use_tabulator=use_tabulator,
        items_rows_compact=items_rows_compact,
        bulk_update_url=url_for("delivery.items_bulk_update", note_id=note_id),
        price_audit_rows=_price_audit_rows_for_note(note_id),
    )


@delivery_bp.route("/<int:note_id>/items/add-product", methods=["POST"])
@login_required
def add_product(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    product = get_product_or_404(g.db, int(request.form.get("product_id", 0)))
    try:
        qty = Decimal(str(request.form.get("quantity", "1")).replace(",", "."))
    except Exception:
        qty = Decimal("1")
    level = getattr(note.customer, "price_level", None) if note.customer else None
    default_unit_price = (product.price_for_level(level) if level else None) or product.effective_sales_price() or Decimal("0")
    manual_price_raw = (request.form.get("unit_price") or "").strip()
    if manual_price_raw:
        try:
            unit_price = Decimal(str(manual_price_raw).replace(",", "."))
        except Exception:
            unit_price = default_unit_price
            flash("Neplatná ruční cena, použita automatická cena produktu.", "warning")
    else:
        unit_price = default_unit_price
    max_order = g.db.query(DeliveryNoteItem).filter(DeliveryNoteItem.delivery_note_id == note_id).count()
    detail_parts = []
    if product.pot_size:
        detail_parts.append(f"Pot: {product.pot_size}")
    if product.description2:
        detail_parts.append(product.description2)
    if product.ean_code:
        detail_parts.append(f"EAN: {product.ean_code}")
    elif product.vbn_code:
        detail_parts.append(f"VBN: {product.vbn_code}")

    item = DeliveryNoteItem(
        delivery_note_id=note_id,
        product_id=product.id,
        item_name=product.description,
        item_description=" | ".join(detail_parts) if detail_parts else None,
        quantity=qty,
        unit=(request.form.get("unit") or product.per_unit or "ks").strip() or "ks",
        unit_price=unit_price,
        line_total=qty * unit_price,
        sort_order=max_order,
        is_manual_item=False,
    )
    g.db.add(item)
    g.db.flush()
    recalc_delivery_note_totals(g.db, note_id)
    g.db.commit()
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/items/add-manual", methods=["POST"])
@login_required
def add_manual(note_id):
    get_delivery_note_or_404(g.db, note_id)
    try:
        qty = Decimal(str(request.form.get("quantity", "1")).replace(",", "."))
        price = Decimal(str(request.form.get("unit_price", "0")).replace(",", "."))
    except Exception:
        qty = Decimal("1")
        price = Decimal("0")
    max_order = g.db.query(DeliveryNoteItem).filter(DeliveryNoteItem.delivery_note_id == note_id).count()
    item = DeliveryNoteItem(
        delivery_note_id=note_id,
        product_id=None,
        item_name=request.form.get("item_name", "").strip(),
        item_description=(request.form.get("item_description") or "").strip() or None,
        quantity=qty,
        unit=(request.form.get("unit") or "ks").strip() or "ks",
        unit_price=price,
        line_total=qty * price,
        sort_order=max_order,
        is_manual_item=True,
    )
    g.db.add(item)
    g.db.flush()
    recalc_delivery_note_totals(g.db, note_id)
    g.db.commit()
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/items/<int:item_id>/delete", methods=["POST"])
@login_required
def item_delete(note_id, item_id):
    item = g.db.query(DeliveryNoteItem).filter(
        DeliveryNoteItem.id == item_id,
        DeliveryNoteItem.delivery_note_id == note_id,
    ).first()
    if item:
        g.db.delete(item)
        g.db.flush()
        recalc_delivery_note_totals(g.db, note_id)
        g.db.commit()
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/items/<int:item_id>/update-price", methods=["POST"])
@login_required
def item_update_price(note_id, item_id):
    item = g.db.query(DeliveryNoteItem).filter(
        DeliveryNoteItem.id == item_id,
        DeliveryNoteItem.delivery_note_id == note_id,
    ).first()
    if not item:
        abort(404)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    raw_price = (request.form.get("unit_price") or "").strip()
    raw_qty = (request.form.get("quantity") or "").strip()
    unit_price = _parse_decimal_input(raw_price, None) if raw_price else None
    quantity = _parse_decimal_input(raw_qty, None) if raw_qty else None

    if raw_price and unit_price is None:
        if is_ajax:
            return jsonify({"ok": False, "error": "Neplatná cena."}), 400
        flash("Neplatná cena položky.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))
    if raw_qty and quantity is None:
        if is_ajax:
            return jsonify({"ok": False, "error": "Neplatné množství."}), 400
        flash("Neplatné množství.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))
    if unit_price is not None and unit_price < 0:
        if is_ajax:
            return jsonify({"ok": False, "error": "Neplatná cena."}), 400
        flash("Neplatná cena položky.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))
    if quantity is not None and quantity <= 0:
        if is_ajax:
            return jsonify({"ok": False, "error": "Množství musí být kladné."}), 400
        flash("Množství musí být kladné.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))
    if unit_price is None and quantity is None:
        if is_ajax:
            return jsonify({"ok": False, "error": "Zadejte cenu nebo množství."}), 400
        return redirect(url_for("delivery.detail", note_id=note_id))

    if unit_price is not None:
        old_price = Decimal(str(item.unit_price or "0"))
        item.unit_price = unit_price
        if old_price != unit_price:
            details = {
                "type": "price_update",
                "from": str(old_price),
                "to": str(unit_price),
                "note_id": note_id,
            }
            audit_log(
                g.db,
                "delivery_note_item",
                item.id,
                getattr(current_user, "id", None),
                "price_update",
                json.dumps(details, ensure_ascii=False),
            )
    if quantity is not None:
        item.quantity = quantity
    item.line_total = (item.quantity or Decimal("0")) * (item.unit_price or Decimal("0"))
    recalc_delivery_note_totals(g.db, note_id)
    g.db.commit()

    if is_ajax:
        return jsonify({
            "ok": True,
            "quantity": str(item.quantity or ""),
            "unit_price": str(item.unit_price or ""),
            "line_total": str(item.line_total or ""),
        })
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/items/<int:item_id>/quick-action", methods=["POST"])
@login_required
def item_quick_action(note_id, item_id):
    item = g.db.query(DeliveryNoteItem).filter(
        DeliveryNoteItem.id == item_id,
        DeliveryNoteItem.delivery_note_id == note_id,
    ).first()
    if not item:
        abort(404)
    action = (request.form.get("action") or "").strip()
    qty = Decimal(str(item.quantity or "0"))
    price = Decimal(str(item.unit_price or "0"))

    if action == "qty_plus":
        qty = qty + Decimal("1")
    elif action == "qty_minus":
        qty = max(Decimal("1"), qty - Decimal("1"))
    elif action == "discount_pct":
        pct = _parse_decimal_input(request.form.get("discount_pct"), Decimal("0")) or Decimal("0")
        if pct < 0:
            pct = Decimal("0")
        if pct > 100:
            pct = Decimal("100")
        price = price * (Decimal("1") - (pct / Decimal("100")))
    elif action == "copy":
        max_order = g.db.query(func.count(DeliveryNoteItem.id)).filter(DeliveryNoteItem.delivery_note_id == note_id).scalar() or 0
        copied = DeliveryNoteItem(
            delivery_note_id=item.delivery_note_id,
            product_id=item.product_id,
            item_name=item.item_name,
            item_description=item.item_description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            line_total=item.line_total,
            sort_order=int(max_order),
            is_manual_item=item.is_manual_item,
        )
        g.db.add(copied)
        audit_log(
            g.db,
            "delivery_note_item",
            item.id,
            getattr(current_user, "id", None),
            "quick_action",
            json.dumps({"type": "copy", "note_id": note_id}, ensure_ascii=False),
        )
        recalc_delivery_note_totals(g.db, note_id)
        g.db.commit()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return {"ok": True}
        return redirect(url_for("delivery.detail", note_id=note_id))
    else:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return {"ok": False, "error": "Neznámá akce"}, 400
        return redirect(url_for("delivery.detail", note_id=note_id))

    old_qty = Decimal(str(item.quantity or "0"))
    old_price = Decimal(str(item.unit_price or "0"))
    item.quantity = qty
    item.unit_price = price
    item.line_total = qty * price
    details = {
        "type": action,
        "qty_from": str(old_qty),
        "qty_to": str(item.quantity),
        "price_from": str(old_price),
        "price_to": str(item.unit_price),
        "note_id": note_id,
    }
    audit_log(
        g.db,
        "delivery_note_item",
        item.id,
        getattr(current_user, "id", None),
        "quick_action",
        json.dumps(details, ensure_ascii=False),
    )
    recalc_delivery_note_totals(g.db, note_id)
    g.db.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return {"ok": True}
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/items/bulk-update", methods=["POST"])
@login_required
def items_bulk_update(note_id):
    get_delivery_note_or_404(g.db, note_id)
    item_ids = []
    for raw in request.form.getlist("item_ids"):
        try:
            item_ids.append(int(raw))
        except Exception:
            pass
    csv_ids = (request.form.get("item_ids_csv") or "").strip()
    if csv_ids:
        for part in csv_ids.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                item_ids.append(int(part))
            except Exception:
                pass
    item_ids = sorted(set(item_ids))
    if not item_ids:
        flash("Bulk edit: vyberte alespoň jednu položku.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))

    qty_set = _parse_decimal_input(request.form.get("quantity_set"))
    price_set = _parse_decimal_input(request.form.get("unit_price_set"))
    discount_pct = _parse_decimal_input(request.form.get("discount_pct"))
    if discount_pct is not None:
        if discount_pct < 0:
            discount_pct = Decimal("0")
        if discount_pct > 100:
            discount_pct = Decimal("100")
    items = (
        g.db.query(DeliveryNoteItem)
        .filter(
            DeliveryNoteItem.delivery_note_id == note_id,
            DeliveryNoteItem.id.in_(item_ids),
        )
        .all()
    )
    if not items:
        flash("Bulk edit: položky nebyly nalezeny.", "warning")
        return redirect(url_for("delivery.detail", note_id=note_id))

    changed = 0
    for item in items:
        old_qty = Decimal(str(item.quantity or "0"))
        old_price = Decimal(str(item.unit_price or "0"))
        if qty_set is not None and qty_set > 0:
            item.quantity = qty_set
        if price_set is not None and price_set >= 0:
            item.unit_price = price_set
        if discount_pct is not None:
            item.unit_price = Decimal(str(item.unit_price or "0")) * (Decimal("1") - (discount_pct / Decimal("100")))
        item.line_total = Decimal(str(item.quantity or "0")) * Decimal(str(item.unit_price or "0"))
        changed += 1
        details = {
            "type": "bulk_update",
            "qty_from": str(old_qty),
            "qty_to": str(item.quantity),
            "price_from": str(old_price),
            "price_to": str(item.unit_price),
            "note_id": note_id,
        }
        audit_log(
            g.db,
            "delivery_note_item",
            item.id,
            getattr(current_user, "id", None),
            "bulk_update",
            json.dumps(details, ensure_ascii=False),
        )
    recalc_delivery_note_totals(g.db, note_id)
    g.db.commit()
    flash(f"Bulk edit uložen: {changed} položek.", "success")
    return redirect(url_for("delivery.detail", note_id=note_id))


@delivery_bp.route("/<int:note_id>/print")
@login_required
def print_(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    return render_template("delivery/print.html", **_ctx(), note=note, sorted_items=_sorted_items_abc(note.items))


@delivery_bp.route("/<int:note_id>/pdf")
@login_required
def pdf(note_id):
    from flask import send_file
    from io import BytesIO
    from app.services.pdf_service import generate_delivery_note_pdf
    note = get_delivery_note_or_404(g.db, note_id)
    company_profile = load_company_profile(current_app.config)
    pdf_bytes = generate_delivery_note_pdf(note, company_profile=company_profile)
    # Inline (otevření v prohlížeči) obchází Brave blokání HTTP downloadů – uložení přes Ctrl+S
    as_attachment = (request.args.get("download") or "0").strip() == "1"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name="dodaci-list-{}.pdf".format(note.document_number),
    )


@delivery_bp.route("/<int:note_id>/issue", methods=["POST"])
@login_required
def issue(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    note.status = "issued"
    g.db.commit()
    return redirect(url_for("delivery.detail", note_id=note_id))
