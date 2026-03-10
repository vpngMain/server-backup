"""Audit log – kdo a kdy změnil entitu."""
from datetime import datetime
from typing import Any
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # product, delivery_note
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[Any] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # create, update, delete
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    details: Mapped[Any] = mapped_column(Text, nullable=True)
