from uuid import UUID

from app.schemas.base import ORMModel


class RefiningComparisonOut(ORMModel):
    tier: int
    raw_item_id: UUID
    raw_code: str
    raw_name: str
    raw_price: int
    refined_item_id: UUID
    refined_code: str
    refined_name: str
    refined_best_price: int
    refined_best_city_id: UUID
    refined_best_city_name: str
