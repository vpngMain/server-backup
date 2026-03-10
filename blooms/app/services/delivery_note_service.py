"""Služby pro dodací listy - číslování, součty."""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import DeliveryNote


def next_document_number(db: Session) -> str:
    """Vygeneruje další číslo dodacího listu: DL-YYYY-0001."""
    year = date.today().year
    prefix = f"DL-{year}-"
    result = (
        db.query(DeliveryNote)
        .filter(DeliveryNote.document_number.like(f"{prefix}%"))
        .order_by(DeliveryNote.id.desc())
        .first()
    )
    if not result:
        return f"{prefix}0001"
    try:
        num = int(result.document_number.split("-")[-1])
        return f"{prefix}{num + 1:04d}"
    except (IndexError, ValueError):
        return f"{prefix}0001"


def recalc_delivery_note_totals(db: Session, delivery_note_id: int) -> None:
    """Přepočítá total_amount u dodacího listu ze součtu položek."""
    db.flush()
    note = db.query(DeliveryNote).filter(DeliveryNote.id == delivery_note_id).first()
    if not note:
        return
    total = sum((item.line_total or Decimal("0")) for item in note.items)
    note.total_amount = total if total else None
    db.flush()
