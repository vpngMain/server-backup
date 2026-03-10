"""Dodaci listy - zakladni routy."""
from datetime import date
from decimal import Decimal

from flask import Blueprint, flash, g, redirect, render_template, request, url_for, abort
from flask_login import login_required, current_user

from app.models import DeliveryNote, DeliveryNoteItem, Customer, Product
from app.services.delivery_note_service import next_document_number, recalc_delivery_note_totals
from app.utils.loaders import get_delivery_note_or_404, get_product_or_404
from app.services.audit_service import log as audit_log

delivery_bp = Blueprint("delivery", __name__)


def _ctx():
    return {"request": request, "current_user": current_user, "dev_skip_auth": False}


def _parse_date(val):
    return date.fromisoformat(val)




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
    return render_template("delivery/detail.html", **_ctx(), note=note, customers=customers, error=err)


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
    unit_price = (product.price_for_level(level) if level else None) or product.effective_sales_price() or Decimal("0")
    max_order = g.db.query(DeliveryNoteItem).filter(DeliveryNoteItem.delivery_note_id == note_id).count()
    item = DeliveryNoteItem(
        delivery_note_id=note_id,
        product_id=product.id,
        item_name=product.description,
        item_description=product.description2,
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


@delivery_bp.route("/<int:note_id>/print")
@login_required
def print_(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    return render_template("delivery/print.html", **_ctx(), note=note)


@delivery_bp.route("/<int:note_id>/pdf")
@login_required
def pdf(note_id):
    from flask import send_file
    from io import BytesIO
    from app.services.pdf_service import generate_delivery_note_pdf
    note = get_delivery_note_or_404(g.db, note_id)
    pdf_bytes = generate_delivery_note_pdf(note)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="dodaci-list-{}.pdf".format(note.document_number),
    )


@delivery_bp.route("/<int:note_id>/issue", methods=["POST"])
@login_required
def issue(note_id):
    note = get_delivery_note_or_404(g.db, note_id)
    note.status = "issued"
    g.db.commit()
    return redirect(url_for("delivery.detail", note_id=note_id))
