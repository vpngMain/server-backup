"""Modely DeliveryNote a DeliveryNoteItem. Nullable: Mapped[Any] kvůli Python 3.14."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Numeric, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utc_now


class DeliveryNote(Base):
    __tablename__ = "delivery_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[Any] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    total_amount: Mapped[Any] = mapped_column(Numeric(18, 2), nullable=True)
    created_by_user_id: Mapped[Any] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="delivery_notes")
    items: Mapped[list["DeliveryNoteItem"]] = relationship(
        "DeliveryNoteItem", back_populates="delivery_note", order_by="DeliveryNoteItem.sort_order"
    )


class DeliveryNoteItem(Base):
    __tablename__ = "delivery_note_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    delivery_note_id: Mapped[int] = mapped_column(ForeignKey("delivery_notes.id"), nullable=False, index=True)
    product_id: Mapped[Any] = mapped_column(ForeignKey("products.id"), nullable=True)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    item_description: Mapped[Any] = mapped_column(String(500), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[Any] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_manual_item: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    delivery_note: Mapped["DeliveryNote"] = relationship("DeliveryNote", back_populates="items")
