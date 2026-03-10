"""Add product price override columns

Revision ID: 003
Revises: 002
Create Date: 2025-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sales_price_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("purchase_price_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("margin_7_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("vip_czk_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("trade_price_override", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "trade_price_override")
    op.drop_column("products", "vip_czk_override")
    op.drop_column("products", "margin_7_override")
    op.drop_column("products", "purchase_price_override")
    op.drop_column("products", "sales_price_override")
