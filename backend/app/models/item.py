import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Item(Base):
    """Itens do jogo. `code` é o unique_name usado pela Albion Online Data Project
    (ex.: T4_BAG); `enchant` é o nível de encantamento (0 = sem encantamento).
    O par (tenant_id, code, enchant) identifica uma linha de preço distinta.
    """

    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", "enchant", name="uq_items_tenant_code_enchant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enchant: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ItemAlias(Base):
    """Nome alternativo/variação de busca para um item (ex.: nome em inglês, abreviação)."""

    __tablename__ = "item_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "item_id", "alias", name="uq_item_aliases_tenant_item_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
