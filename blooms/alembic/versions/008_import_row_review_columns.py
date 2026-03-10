"""ImportRow: source_*, computed_*, current_effective_*, delta_*, match_confidence, review_flags_json

Revision ID: 008
Revises: 007
Create Date: 2025-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Source (from Excel)
    op.add_column("import_rows", sa.Column("source_description", sa.String(500), nullable=True))
    op.add_column("import_rows", sa.Column("source_pot_size", sa.String(100), nullable=True))
    op.add_column("import_rows", sa.Column("source_sales_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_qty", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_unit_per_cc", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("source_ean", sa.String(50), nullable=True))
    op.add_column("import_rows", sa.Column("source_vbn", sa.String(50), nullable=True))
    # Computed (business formulas)
    op.add_column("import_rows", sa.Column("computed_purchase_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_margin_7_price", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_vip_eur", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_vip_czk", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_d1", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("computed_d4", sa.Numeric(18, 4), nullable=True))
    # Current effective (from product at match time)
    op.add_column("import_rows", sa.Column("current_effective_vip_eur", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("current_effective_vip_czk", sa.Numeric(18, 4), nullable=True))
    op.add_column("import_rows", sa.Column("current_effective_d1", sa.Numeric(18, 4), nullable=True))
    # Deltas and review
    op.add_column("import_rows", sa.Column("delta_vip_eur_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("delta_vip_czk_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("delta_d1_pct", sa.Numeric(8, 2), nullable=True))
    op.add_column("import_rows", sa.Column("match_confidence", sa.String(20), nullable=True))
    op.add_column("import_rows", sa.Column("review_flags_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("import_rows", "review_flags_json")
    op.drop_column("import_rows", "match_confidence")
    op.drop_column("import_rows", "delta_d1_pct")
    op.drop_column("import_rows", "delta_vip_czk_pct")
    op.drop_column("import_rows", "delta_vip_eur_pct")
    op.drop_column("import_rows", "current_effective_d1")
    op.drop_column("import_rows", "current_effective_vip_czk")
    op.drop_column("import_rows", "current_effective_vip_eur")
    op.drop_column("import_rows", "computed_d4")
    op.drop_column("import_rows", "computed_d1")
    op.drop_column("import_rows", "computed_vip_czk")
    op.drop_column("import_rows", "computed_vip_eur")
    op.drop_column("import_rows", "computed_margin_7_price")
    op.drop_column("import_rows", "computed_purchase_price")
    op.drop_column("import_rows", "source_vbn")
    op.drop_column("import_rows", "source_ean")
    op.drop_column("import_rows", "source_unit_per_cc")
    op.drop_column("import_rows", "source_qty")
    op.drop_column("import_rows", "source_sales_price")
    op.drop_column("import_rows", "source_pot_size")
    op.drop_column("import_rows", "source_description")
