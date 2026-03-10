"""Statistiky pro dashboard: nejlepší odběratelé, nejprodávanější produkty, dodací listy v čase."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Customer, DeliveryNote, DeliveryNoteItem, Product


def top_customers_by_revenue(db: Session, limit: int = 8):
    """Nejlepší odběratelé podle celkových tržeb (suma total_amount dodacích listů)."""
    sub = (
        db.query(
            DeliveryNote.customer_id,
            func.coalesce(func.sum(DeliveryNote.total_amount), 0).label("total"),
        )
        .filter(DeliveryNote.status != "cancelled")
        .group_by(DeliveryNote.customer_id)
    ).subquery()

    rows = (
        db.query(Customer.company_name, sub.c.total)
        .join(sub, Customer.id == sub.c.customer_id)
        .order_by(sub.c.total.desc())
        .limit(limit)
        .all()
    )
    return [{"name": name, "revenue": float(total) if total else 0.0} for name, total in rows]


def top_products_by_quantity(db: Session, limit: int = 10):
    """Nejprodávanější produkty podle celkového množství na dodacích listech."""
    rows = (
        db.query(
            Product.description,
            func.coalesce(func.sum(DeliveryNoteItem.quantity), 0).label("qty"),
        )
        .select_from(DeliveryNoteItem)
        .join(DeliveryNote, DeliveryNoteItem.delivery_note_id == DeliveryNote.id)
        .outerjoin(Product, DeliveryNoteItem.product_id == Product.id)
        .filter(DeliveryNote.status != "cancelled")
        .group_by(Product.id, Product.description)
        .order_by(func.sum(DeliveryNoteItem.quantity).desc())
        .limit(limit)
        .all()
    )
    # Položky bez produktu (ruční) mají description z item_name; u nás máme product_id
    out = []
    for desc, qty in rows:
        label = (desc or "Ruční položka").strip()
        if len(label) > 40:
            label = label[:37] + "..."
        out.append({"name": label, "quantity": float(qty)})
    return out


def delivery_notes_by_month(db: Session, months: int = 12):
    """Počet dodacích listů a tržby po měsících (zpětně od dneška). SQLite‑kompatibilní."""
    return _delivery_notes_by_month_sqlite(db, months)


def _delivery_notes_by_month_sqlite(db: Session, months: int):
    """Počet a tržby po měsících pro SQLite (bez date_trunc)."""
    since = datetime.now(timezone.utc).date() - timedelta(days=months * 31)
    rows = (
        db.query(
            DeliveryNote.issue_date,
            DeliveryNote.total_amount,
        )
        .filter(
            DeliveryNote.issue_date >= since,
            DeliveryNote.status != "cancelled",
        )
        .all()
    )
    by_month = {}
    for issue_date, total in rows:
        key = issue_date.replace(day=1) if hasattr(issue_date, "replace") else issue_date
        if key not in by_month:
            by_month[key] = {"count": 0, "revenue": Decimal("0")}
        by_month[key]["count"] += 1
        by_month[key]["revenue"] += (total if total is not None else Decimal("0"))
    sorted_months = sorted(by_month.keys())
    return [
        {
            "month": m.strftime("%Y-%m"),
            "label": m.strftime("%m/%Y"),
            "count": by_month[m]["count"],
            "revenue": float(by_month[m]["revenue"]),
        }
        for m in sorted_months
    ]
