"""initial schema: tenants, users, memberships, cities, items, prices, alerts + RLS

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas com tenant_id que recebem a mesma policy de RLS.
_TENANT_TABLES = ["users", "memberships", "cities", "items", "prices", "alerts"]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("role", sa.String(30), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "cities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_cities_tenant_code"),
    )

    op.create_table(
        "items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unique_name", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "unique_name", name="uq_items_tenant_unique_name"),
    )

    op.create_table(
        "prices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False
        ),
        sa.Column(
            "city_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cities.id"), nullable=False
        ),
        sa.Column("sell_price_min", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sell_price_max", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("buy_price_min", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("buy_price_max", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quality", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_prices_item_city", "prices", ["item_id", "city_id", "collected_at"])

    op.create_table(
        "alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False
        ),
        sa.Column(
            "city_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cities.id"), nullable=False
        ),
        sa.Column("target_price", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # `tenants` fica de fora da RLS por definição: é a tabela que define os tenants.
    for table in _TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("alerts")
    op.drop_index("ix_prices_item_city", table_name="prices")
    op.drop_table("prices")
    op.drop_table("items")
    op.drop_table("cities")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
