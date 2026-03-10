"""Načtení entit podle ID s 404 při neexistenci – jednotná validace vstupů."""
from flask import abort
from sqlalchemy.orm import Session

from app.models import Product, Customer, DeliveryNote, ImportBatch, ImportFile, ImportRow, User


def get_product_or_404(db: Session, product_id: int) -> Product:
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        abort(404)
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        abort(404)
    return p


def get_customer_or_404(db: Session, customer_id: int) -> Customer:
    try:
        cid = int(customer_id)
    except (TypeError, ValueError):
        abort(404)
    c = db.query(Customer).filter(Customer.id == cid).first()
    if not c:
        abort(404)
    return c


def get_delivery_note_or_404(db: Session, note_id: int) -> DeliveryNote:
    try:
        nid = int(note_id)
    except (TypeError, ValueError):
        abort(404)
    n = db.query(DeliveryNote).filter(DeliveryNote.id == nid).first()
    if not n:
        abort(404)
    return n


def get_import_batch_or_404(db: Session, batch_id: int) -> ImportBatch:
    try:
        bid = int(batch_id)
    except (TypeError, ValueError):
        abort(404)
    b = db.query(ImportBatch).filter(ImportBatch.id == bid).first()
    if not b:
        abort(404)
    return b


def get_import_file_or_404(db: Session, batch_id: int, file_id: int) -> ImportFile:
    try:
        fid = int(file_id)
    except (TypeError, ValueError):
        abort(404)
    f = db.query(ImportFile).filter(
        ImportFile.id == fid,
        ImportFile.import_batch_id == batch_id,
    ).first()
    if not f:
        abort(404)
    return f


def get_import_row_or_404(db: Session, file_id: int, row_id: int):
    try:
        rid = int(row_id)
        fid = int(file_id)
    except (TypeError, ValueError):
        abort(404)
    row = db.query(ImportRow).filter(
        ImportRow.id == rid,
        ImportRow.import_file_id == fid,
    ).first()
    if not row:
        abort(404)
    return row


def get_user_or_404(db: Session, user_id: int) -> User:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        abort(404)
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        abort(404)
    return u
