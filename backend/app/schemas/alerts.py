from uuid import UUID

from pydantic import BaseModel

from app.schemas.base import TimestampedModel


class AlertCreate(BaseModel):
    item_id: UUID
    city_id: UUID
    target_price: int


class AlertOut(TimestampedModel):
    item_id: UUID
    city_id: UUID
    target_price: int
    is_active: bool
