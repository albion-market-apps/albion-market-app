import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Price(Base):
    """Snapshot de preço de um item em uma cidade, coletado pelo worker."""

    __tablename__ = "prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), nullable=False
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id"), nullable=False
    )
    sell_price_min: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sell_price_max: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    buy_price_min: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    buy_price_max: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quality: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
