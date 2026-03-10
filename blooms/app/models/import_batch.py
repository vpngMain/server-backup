"""Modely pro import. Nullable sloupce: Mapped[Any] kvůli Python 3.14/SQLAlchemy."""
from datetime import datetime
from typing import Any
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db import Base, utc_now


class ImportStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class RowAction(str, enum.Enum):
    new = "new"
    matched = "matched"
    skipped = "skipped"
    error = "error"


class MatchConfidence(str, enum.Enum):
    """Jak byl řádek přiřazen k produktu."""
    exact_match = "exact_match"  # EAN nebo VBN
    probable_match = "probable_match"  # product_key (description + pot_size)
    no_match = "no_match"


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_folder: Mapped[str] = mapped_column(String(1000), nullable=False)
    shipping_eur: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)  # doprava v EUR k tomuto importu
    exchange_rate: Mapped[Any] = mapped_column(Numeric(18, 6), nullable=True)  # kurz pro VIP CZK
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    new_products: Mapped[int] = mapped_column(Integer, default=0)
    existing_products: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=ImportStatus.completed.value)
    created_by_user_id: Mapped[Any] = mapped_column(ForeignKey("users.id"), nullable=True)

    import_files: Mapped[list["ImportFile"]] = relationship("ImportFile", back_populates="import_batch", order_by="ImportFile.id")


class ImportFile(Base):
    __tablename__ = "import_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    order_number: Mapped[Any] = mapped_column(String(100), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    new_products: Mapped[int] = mapped_column(Integer, default=0)
    existing_products: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=ImportStatus.completed.value)
    report_text: Mapped[Any] = mapped_column(Text, nullable=True)

    import_batch: Mapped["ImportBatch"] = relationship("ImportBatch", back_populates="import_files")
    rows: Mapped[list["ImportRow"]] = relationship("ImportRow", back_populates="import_file", order_by="ImportRow.row_index")


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_file_id: Mapped[int] = mapped_column(ForeignKey("import_files.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data_json: Mapped[Any] = mapped_column(Text, nullable=True)
    matched_product_id: Mapped[Any] = mapped_column(ForeignKey("products.id"), nullable=True)
    action_taken: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Any] = mapped_column(String(500), nullable=True)

    # Source (z Excelu) – pro přehled bez parsování raw_data_json
    source_description: Mapped[Any] = mapped_column(String(500), nullable=True)
    source_pot_size: Mapped[Any] = mapped_column(String(100), nullable=True)
    source_sales_price: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    source_qty: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    source_unit_per_cc: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    source_ean: Mapped[Any] = mapped_column(String(50), nullable=True)
    source_vbn: Mapped[Any] = mapped_column(String(50), nullable=True)
    # Vypočtené ceny (vzorce)
    computed_purchase_price: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    computed_margin_7_price: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    computed_vip_eur: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    computed_vip_czk: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    computed_d1: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    computed_d4: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    # Aktuální efektivní ceny v produktu v okamžiku match
    current_effective_vip_eur: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    current_effective_vip_czk: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    current_effective_d1: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    # Delta % (computed vs current) pro review
    delta_vip_eur_pct: Mapped[Any] = mapped_column(Numeric(8, 2), nullable=True)
    delta_vip_czk_pct: Mapped[Any] = mapped_column(Numeric(8, 2), nullable=True)
    delta_d1_pct: Mapped[Any] = mapped_column(Numeric(8, 2), nullable=True)
    match_confidence: Mapped[Any] = mapped_column(String(20), nullable=True)  # exact_match | probable_match | no_match
    review_flags_json: Mapped[Any] = mapped_column(Text, nullable=True)  # JSON seznam příznaků

    import_file: Mapped["ImportFile"] = relationship("ImportFile", back_populates="rows")
