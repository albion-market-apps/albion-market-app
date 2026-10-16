"""items: code/name/enchant + item_aliases; prices: qty + índice por (item, city, collected_at DESC)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    # items: unique_name/display_name -> code/name (nomenclatura alinhada com o
    # catálogo real do jogo) + enchant (nível de encantamento).
    op.alter_column("items", "unique_name", new_column_name="code")
    op.alter_column("items", "display_name", new_column_name="name")
    op.add_column("items", sa.Column("enchant", sa.Integer(), nullable=False, server_default="0"))

    op.drop_constraint("uq_items_tenant_unique_name", "items", type_="unique")
    op.create_unique_constraint(
        "uq_items_tenant_code_enchant", "items", ["tenant_id", "code", "enchant"]
    )

    # Busca textual em code/name: acelera ILIKE com índice trigram seria o ideal,
    # mas evitamos a extensão pg_trgm por ora (custo/complexidade) — índice btree
    # normal já ajuda em prefixo e ORDER BY; ver nota em docs/claude.md.
    op.create_index("ix_items_tenant_code", "items", ["tenant_id", "code"])
    op.create_index("ix_items_tenant_name", "items", ["tenant_id", "name"])

    op.create_table(
        "item_aliases",
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
        sa.Column("alias", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "item_id", "alias", name="uq_item_aliases_tenant_item_alias"
        ),
    )
    op.create_index("ix_item_aliases_tenant_alias", "item_aliases", ["tenant_id", "alias"])
    _enable_rls("item_aliases")

    # prices: soma de quantidade negociada (usada na agregação 1h/24h) e índice
    # dedicado para as consultas de GET /prices (raw e agregado).
    op.add_column("prices", sa.Column("qty", sa.BigInteger(), nullable=False, server_default="0"))

    op.drop_index("ix_prices_item_city", table_name="prices")
    op.create_index(
        "ix_prices_item_city_collected",
        "prices",
        ["item_id", "city_id", sa.text("collected_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_prices_item_city_collected", table_name="prices")
    op.create_index("ix_prices_item_city", "prices", ["item_id", "city_id", "collected_at"])
    op.drop_column("prices", "qty")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON item_aliases")
    op.drop_index("ix_item_aliases_tenant_alias", table_name="item_aliases")
    op.drop_table("item_aliases")

    op.drop_index("ix_items_tenant_name", table_name="items")
    op.drop_index("ix_items_tenant_code", table_name="items")
    op.drop_constraint("uq_items_tenant_code_enchant", "items", type_="unique")
    op.create_unique_constraint("uq_items_tenant_unique_name", "items", ["tenant_id", "code"])
    op.drop_column("items", "enchant")
    op.alter_column("items", "name", new_column_name="display_name")
    op.alter_column("items", "code", new_column_name="unique_name")
