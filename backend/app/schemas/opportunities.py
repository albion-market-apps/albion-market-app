from datetime import datetime
from uuid import UUID

from app.schemas.base import ORMModel


class TradeOpportunityOut(ORMModel):
    item_id: UUID
    item_code: str
    item_name: str
    item_tier: int
    item_enchant: int
    buy_city_id: UUID
    buy_city_name: str
    buy_price: int
    sell_city_id: UUID
    sell_city_name: str
    sell_price: int  # venda instantânea
    sell_order_price: int  # venda por ordem própria (0 = sem oferta de venda ativa lá)
    profit: int
    collected_at: datetime
