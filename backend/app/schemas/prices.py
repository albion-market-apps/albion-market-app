from datetime import datetime
from uuid import UUID

from app.schemas.base import ORMModel


class PriceRawOut(ORMModel):
    id: UUID
    item_id: UUID
    city_id: UUID
    sell_price_min: int
    sell_price_max: int
    buy_price_min: int
    buy_price_max: int
    quality: int
    qty: int
    collected_at: datetime


class PriceBucketOut(ORMModel):
    """Agregação por bucket de tempo (1h ou 24h) e cidade.

    `sell_*` é calculado sobre `sell_price_min` (menor preço de venda — o que
    um comprador pagaria); `buy_*` é calculado sobre `buy_price_max` (maior
    oferta de compra — o que um vendedor receberia). `qty_sum` é a soma da
    quantidade negociada no bucket.
    """

    city_id: UUID
    bucket_start: datetime
    sell_min: int
    sell_avg: float
    sell_max: int
    buy_min: int
    buy_avg: float
    buy_max: int
    qty_sum: int


class PricesResponse(ORMModel):
    item_id: UUID
    agg: str
    data: list[PriceRawOut] | list[PriceBucketOut]
