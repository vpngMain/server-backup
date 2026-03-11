"""Model User."""
from datetime import datetime
from typing import Any

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.db import Base, utc_now


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.user.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    products_columns_json: Mapped[Any] = mapped_column(Text, nullable=True)
    tabulator_state_json: Mapped[Any] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    def is_admin(self) -> bool:
        return self.role == UserRole.admin.value

    # Flask-Login
    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False
