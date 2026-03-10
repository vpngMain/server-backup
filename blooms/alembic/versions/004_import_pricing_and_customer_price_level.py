"""Import: doprava EUR, kurz; Product: D4; Customer: cenová hladina

Revision ID: 004
Revises: 003
Create Date: 2025-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("import_batches", sa.Column("shipping_eur", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_batches", sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True))
    op.add_column("products", sa.Column("d4_price_imported", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("d4_price_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("vip_eur_imported", sa.Numeric(18, 4), nullable=True))
    op.add_column("products", sa.Column("vip_eur_override", sa.Numeric(18, 4), nullable=True))
    op.add_column("customers", sa.Column("price_level", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "price_level")
    op.drop_column("products", "vip_eur_override")
    op.drop_column("products", "vip_eur_imported")
    op.drop_column("products", "d4_price_override")
    op.drop_column("products", "d4_price_imported")
    op.drop_column("import_batches", "exchange_rate")
    op.drop_column("import_batches", "shipping_eur")
