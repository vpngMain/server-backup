"""Model Customer. Nullable sloupce: Mapped[Any] kvůli Python 3.14/SQLAlchemy."""
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utc_now


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    ico: Mapped[Any] = mapped_column(String(20), nullable=True)
    dic: Mapped[Any] = mapped_column(String(20), nullable=True)
    street: Mapped[Any] = mapped_column(String(300), nullable=True)
    city: Mapped[Any] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[Any] = mapped_column(String(20), nullable=True)
    country: Mapped[Any] = mapped_column(String(100), nullable=True)
    provozovna_street: Mapped[Any] = mapped_column(String(300), nullable=True)
    provozovna_city: Mapped[Any] = mapped_column(String(100), nullable=True)
    provozovna_zip_code: Mapped[Any] = mapped_column(String(20), nullable=True)
    provozovna_country: Mapped[Any] = mapped_column(String(100), nullable=True)
    contact_person: Mapped[Any] = mapped_column(String(200), nullable=True)
    phone: Mapped[Any] = mapped_column(String(50), nullable=True)
    email: Mapped[Any] = mapped_column(String(200), nullable=True)
    note: Mapped[Any] = mapped_column(Text, nullable=True)
    price_level: Mapped[Any] = mapped_column(String(20), nullable=True)  # VIP_EUR, VIP_CZK, D4, D1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    delivery_notes: Mapped[list["DeliveryNote"]] = relationship("DeliveryNote", back_populates="customer")
