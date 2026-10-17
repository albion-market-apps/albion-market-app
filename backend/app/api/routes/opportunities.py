from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.rls import get_current_tenant_id, get_tenant_db
from app.models.city import City
from app.models.item import Item
from app.schemas.opportunities import TradeOpportunityOut
from app.services.opportunities import (
    TradeOpportunity,
    best_trades_for_items,
    best_trades_from_city,
    best_trades_global,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

MAX_FAVORITE_ITEMS = 4


def _enrich(
    db: Session, tenant_id: UUID, trades: list[TradeOpportunity]
) -> list[TradeOpportunityOut]:
    """Junta nome de item/cidade nas oportunidades calculadas — o cálculo em
    si (`app.services.opportunities`) só lida com ids, pra não acoplar a
    lógica de arbitragem a schema de resposta."""
    if not trades:
        return []

    item_ids = {trade.item_id for trade in trades}
    city_ids = {trade.buy_city_id for trade in trades} | {trade.sell_city_id for trade in trades}

    items = {
        item.id: item
        for item in db.scalars(
            select(Item).where(Item.tenant_id == tenant_id, Item.id.in_(item_ids))
        )
    }
    cities = {
        city.id: city
        for city in db.scalars(
            select(City).where(City.tenant_id == tenant_id, City.id.in_(city_ids))
        )
    }

    out = []
    for trade in trades:
        item = items.get(trade.item_id)
        buy_city = cities.get(trade.buy_city_id)
        sell_city = cities.get(trade.sell_city_id)
        if item is None or buy_city is None or sell_city is None:
            continue  # defensivo — RLS já garante mesmo tenant, não deveria faltar
        out.append(
            TradeOpportunityOut(
                item_id=trade.item_id,
                item_code=item.code,
                item_name=item.name,
                item_tier=item.tier,
                item_enchant=item.enchant,
                buy_city_id=trade.buy_city_id,
                buy_city_name=buy_city.name,
                buy_price=trade.buy_price,
                sell_city_id=trade.sell_city_id,
                sell_city_name=sell_city.name,
                sell_price=trade.sell_price,
                profit=trade.profit,
                collected_at=trade.collected_at,
            )
        )
    return out


def _parse_item_ids(raw: str) -> list[UUID]:
    try:
        return [UUID(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="item_ids inválido — use UUIDs separados por vírgula"
        ) from exc


@router.get("/favorites", response_model=list[TradeOpportunityOut])
def favorites_opportunities(
    item_ids: str = Query(..., description="até 4 UUIDs de item separados por vírgula"),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[TradeOpportunityOut]:
    """Melhor par compra/venda pra cada item da lista de favoritos — cidade
    de compra livre (a mais barata entre todas), cidade de venda livre (a
    melhor oferta entre todas). Itens sem preço coletado ainda, ou sem
    combinação compra/venda válida, simplesmente não aparecem na resposta
    (o front decide como sinalizar "sem dado ainda" comparando com a lista
    de `item_ids` pedida)."""
    parsed_ids = _parse_item_ids(item_ids)
    if not parsed_ids:
        raise HTTPException(status_code=422, detail="informe ao menos um item_id")
    if len(parsed_ids) > MAX_FAVORITE_ITEMS:
        raise HTTPException(status_code=422, detail=f"no máximo {MAX_FAVORITE_ITEMS} itens")

    trades = best_trades_for_items(db, tenant_id, parsed_ids)
    return _enrich(db, tenant_id, trades)


@router.get("/best-from-city", response_model=list[TradeOpportunityOut])
def best_from_city(
    city_id: UUID = Query(..., description="cidade onde o usuário está agora"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[TradeOpportunityOut]:
    """Ranking dos itens mais lucrativos pra comprar em `city_id` agora e
    vender em outra cidade — todo o catálogo do tenant com preço coletado,
    ordenado por lucro decrescente (só lucro positivo entra)."""
    trades = best_trades_from_city(db, tenant_id, city_id, limit=limit)
    return _enrich(db, tenant_id, trades)


@router.get("/top", response_model=list[TradeOpportunityOut])
def top_opportunities(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[TradeOpportunityOut]:
    """Ranking dos itens mais lucrativos do catálogo inteiro, sem travar
    cidade de compra nem de venda — "o que está mais lucrativo agora,
    onde quer que seja". Calculado na hora a cada chamada (não
    pré-calculado nem cacheado por hora — ver `best_trades_global`)."""
    trades = best_trades_global(db, tenant_id, limit=limit)
    return _enrich(db, tenant_id, trades)
