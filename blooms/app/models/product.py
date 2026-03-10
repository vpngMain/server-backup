"""Model Product. Použito Mapped[Any] u nullable sloupců kvůli kompatibilitě s Python 3.14/SQLAlchemy."""
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import String, Boolean, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utc_now


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description2: Mapped[Any] = mapped_column(String(500), nullable=True)
    pot_size: Mapped[Any] = mapped_column(String(100), nullable=True, index=True)
    product_key_normalized: Mapped[str] = mapped_column(String(600), unique=True, nullable=False)

    ean_code: Mapped[Any] = mapped_column(String(50), nullable=True)
    vbn_code: Mapped[Any] = mapped_column(String(50), nullable=True)
    plant_passport_no: Mapped[Any] = mapped_column(String(100), nullable=True)
    customer_line_info: Mapped[Any] = mapped_column(String(500), nullable=True)
    image_reference: Mapped[Any] = mapped_column(String(500), nullable=True)

    qty: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    ordered_qty: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    per_unit: Mapped[Any] = mapped_column(String(50), nullable=True)
    qty_per_shelf: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    shelf_per_cc: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    unit_per_cc: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    sales_price_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    amount_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_price_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    margin_7_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    vip_eur_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    vip_czk_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    trade_price_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    d4_price_imported: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)  # D4 – konkurence / ruční

    # Přepsané ceny (admin)
    sales_price_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_price_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    margin_7_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    vip_eur_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    vip_czk_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    trade_price_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)
    d4_price_override: Mapped[Any] = mapped_column(Numeric(18, 4), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_imported_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    last_imported_at: Mapped[Any] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    def effective_sales_price(self) -> Decimal | None:
        """Cena pro dodací listy a výpočty: přepis z DB, jinak z importu."""
        return self.sales_price_override if self.sales_price_override is not None else self.sales_price_imported

    def effective_purchase_price(self) -> Decimal | None:
        return self.purchase_price_override if self.purchase_price_override is not None else self.purchase_price_imported

    def effective_margin_7(self) -> Decimal | None:
        return self.margin_7_override if self.margin_7_override is not None else self.margin_7_imported

    def effective_vip_czk(self) -> Decimal | None:
        return self.vip_czk_override if self.vip_czk_override is not None else self.vip_czk_imported

    def effective_trade_price(self) -> Decimal | None:
        return self.trade_price_override if self.trade_price_override is not None else self.trade_price_imported

    def effective_d4_price(self) -> Decimal | None:
        return self.d4_price_override if self.d4_price_override is not None else self.d4_price_imported

    def price_for_level(self, level: str) -> Decimal | None:
        """Cena podle cenové hladiny: VIP_EUR, VIP_CZK, D4, D1 (obchod)."""
        if level == "VIP_EUR":
            return self.effective_vip_eur()
        if level == "VIP_CZK":
            return self.effective_vip_czk()
        if level == "D4":
            return self.effective_d4_price()
        if level == "D1":
            return self.effective_trade_price()
        return None

    def effective_vip_eur(self) -> Decimal | None:
        return self.vip_eur_override if self.vip_eur_override is not None else self.vip_eur_imported

    def margin_percent(self, selling_price: Decimal | None, cost: Decimal | None) -> Decimal | None:
        """Marže v %: (selling - cost) / selling * 100. cost = cena+doprava (nakup)."""
        if selling_price is None or cost is None or selling_price <= 0:
            return None
        try:
            return ((selling_price - cost) / selling_price * 100).quantize(Decimal("0.01"))
        except Exception:
            return None
