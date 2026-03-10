"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("description2", sa.String(500), nullable=True),
        sa.Column("pot_size", sa.String(100), nullable=True),
        sa.Column("product_key_normalized", sa.String(600), nullable=False),
        sa.Column("ean_code", sa.String(50), nullable=True),
        sa.Column("vbn_code", sa.String(50), nullable=True),
        sa.Column("plant_passport_no", sa.String(100), nullable=True),
        sa.Column("customer_line_info", sa.String(500), nullable=True),
        sa.Column("image_reference", sa.String(500), nullable=True),
        sa.Column("qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("ordered_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("per_unit", sa.String(50), nullable=True),
        sa.Column("qty_per_shelf", sa.Numeric(18, 4), nullable=True),
        sa.Column("shelf_per_cc", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_per_cc", sa.Numeric(18, 4), nullable=True),
        sa.Column("sales_price_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("amount_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("purchase_price_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("margin_7_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("vip_czk_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("trade_price_imported", sa.Numeric(18, 4), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("first_imported_at", sa.DateTime(), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_product_key_normalized", "products", ["product_key_normalized"], unique=True)
    op.create_index("ix_products_description", "products", ["description"], unique=False)
    op.create_index("ix_products_pot_size", "products", ["pot_size"], unique=False)

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_folder", sa.String(1000), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("new_products", sa.Integer(), nullable=True),
        sa.Column("existing_products", sa.Integer(), nullable=True),
        sa.Column("error_rows", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_import_batches_created_by_user_id_users"),
    )

    op.create_table(
        "import_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("order_number", sa.String(100), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("new_products", sa.Integer(), nullable=True),
        sa.Column("existing_products", sa.Integer(), nullable=True),
        sa.Column("error_rows", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("report_text", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], name="fk_import_files_import_batch_id_import_batches"),
    )

    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_file_id", sa.Integer(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("raw_data_json", sa.Text(), nullable=True),
        sa.Column("matched_product_id", sa.Integer(), nullable=True),
        sa.Column("action_taken", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["import_file_id"], ["import_files.id"], name="fk_import_rows_import_file_id_import_files"),
        sa.ForeignKeyConstraint(["matched_product_id"], ["products.id"], name="fk_import_rows_matched_product_id_products"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(300), nullable=False),
        sa.Column("ico", sa.String(20), nullable=True),
        sa.Column("dic", sa.String(20), nullable=True),
        sa.Column("street", sa.String(300), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_company_name", "customers", ["company_name"], unique=False)

    op.create_table(
        "delivery_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_delivery_notes_customer_id_customers"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_delivery_notes_created_by_user_id_users"),
    )
    op.create_index("ix_delivery_notes_document_number", "delivery_notes", ["document_number"], unique=True)

    op.create_table(
        "delivery_note_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("delivery_note_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("item_name", sa.String(500), nullable=False),
        sa.Column("item_description", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_manual_item", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["delivery_note_id"], ["delivery_notes.id"], name="fk_delivery_note_items_delivery_note_id_delivery_notes"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_delivery_note_items_product_id_products"),
    )


def downgrade() -> None:
    op.drop_table("delivery_note_items")
    op.drop_table("delivery_notes")
    op.drop_table("customers")
    op.drop_table("import_rows")
    op.drop_table("import_files")
    op.drop_table("import_batches")
    op.drop_table("products")
    op.drop_table("users")
