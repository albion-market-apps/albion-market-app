from app.schemas.base import ORMModel, TimestampedModel


class ItemOut(TimestampedModel):
    code: str
    name: str
    tier: int
    enchant: int


class ItemsPage(ORMModel):
    items: list[ItemOut]
    page: int
    page_size: int
    total: int
