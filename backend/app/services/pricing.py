"""Consultas de busca de itens e preços (raw/agregado), e gravação de preços
coletados pelo worker (upsert + invalidação de cache).

Todas as funções aqui assumem que a `Session` recebida já está dentro de uma
transação com `SET LOCAL app.tenant_id` aplicado (ver `app.db.rls.get_tenant_db`)
— nenhuma função filtra tenant_id "extra" por segurança; a RLS do Postgres é
quem garante o isolamento. O filtro `tenant_id == tenant_id` nas queries abaixo
existe para aproveitar os índices compostos (tenant_id, ...) e não é a camada
de segurança em si.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_item_prices_cache
from app.models.city import City
from app.models.item import Item, ItemAlias
from app.models.price import Price
from app.schemas.prices import PriceBucketOut, PriceRawOut

RAW_PRICES_LIMIT_PER_CITY = 200


def search_items(
    db: Session, tenant_id: UUID, query: str | None, page: int, page_size: int
) -> tuple[list[Item], int]:
    """Busca itens por `code`/`name`/aliases, com relevância simples:
    match exato > prefixo > substring > só via alias.
    """
    filters = [Item.tenant_id == tenant_id]
    rank_expr = None

    if query:
        q = query.strip()
        prefix, contains = f"{q}%", f"%{q}%"
        alias_match = exists(
            select(ItemAlias.id).where(
                ItemAlias.tenant_id == tenant_id,
                ItemAlias.item_id == Item.id,
                ItemAlias.alias.ilike(contains),
            )
        )
        filters.append(or_(Item.code.ilike(contains), Item.name.ilike(contains), alias_match))
        rank_expr = case(
            (or_(Item.code.ilike(q), Item.name.ilike(q)), 0),
            (or_(Item.code.ilike(prefix), Item.name.ilike(prefix)), 1),
            (or_(Item.code.ilike(contains), Item.name.ilike(contains)), 2),
            else_=3,
        )

    total = db.scalar(select(func.count()).select_from(Item).where(*filters)) or 0

    stmt = select(Item).where(*filters)
    stmt = (
        stmt.order_by(rank_expr.asc(), Item.name.asc())
        if rank_expr is not None
        else stmt.order_by(Item.name.asc())
    )
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = list(db.scalars(stmt))
    return items, total


def resolve_city_ids(db: Session, tenant_id: UUID, codes: list[str]) -> list[UUID]:
    if not codes:
        return []
    stmt = select(City.id).where(City.tenant_id == tenant_id, City.code.in_(codes))
    return [row[0] for row in db.execute(stmt).all()]


def query_raw_prices(
    db: Session,
    tenant_id: UUID,
    item_id: UUID,
    city_ids: list[UUID] | None,
    from_: datetime | None,
    to_: datetime | None,
    limit_per_city: int = RAW_PRICES_LIMIT_PER_CITY,
) -> list[PriceRawOut]:
    """Últimos `limit_per_city` registros por cidade, via CTE com row_number()
    particionado por city_id — usa o índice (item_id, city_id, collected_at DESC).

    `city_ids=None` significa "sem filtro de cidade" (todas as cidades do
    tenant). `city_ids=[]` significa "o caller pediu cidades específicas e
    nenhuma bateu" — deve retornar vazio, não cair para "todas as cidades"
    (ver bug corrigido em `app.api.routes.prices`: `cities=Lymhurst,Martlock`
    com capitalização/código que não existe não pode virar "sem filtro").
    """
    filters = [Price.tenant_id == tenant_id, Price.item_id == item_id]
    if city_ids is not None:
        filters.append(Price.city_id.in_(city_ids))
    if from_:
        filters.append(Price.collected_at >= from_)
    if to_:
        filters.append(Price.collected_at <= to_)

    rn = (
        func.row_number()
        .over(partition_by=Price.city_id, order_by=Price.collected_at.desc())
        .label("rn")
    )
    ranked = (
        select(
            Price.id,
            Price.item_id,
            Price.city_id,
            Price.sell_price_min,
            Price.sell_price_max,
            Price.buy_price_min,
            Price.buy_price_max,
            Price.quality,
            Price.qty,
            Price.collected_at,
            rn,
        )
        .where(*filters)
        .cte("ranked_prices")
    )

    stmt = (
        select(ranked)
        .where(ranked.c.rn <= limit_per_city)
        .order_by(ranked.c.city_id, ranked.c.collected_at.desc())
    )

    rows = db.execute(stmt).all()
    return [
        PriceRawOut(
            id=row.id,
            item_id=row.item_id,
            city_id=row.city_id,
            sell_price_min=row.sell_price_min,
            sell_price_max=row.sell_price_max,
            buy_price_min=row.buy_price_min,
            buy_price_max=row.buy_price_max,
            quality=row.quality,
            qty=row.qty,
            collected_at=row.collected_at,
        )
        for row in rows
    ]


def query_aggregated_prices(
    db: Session,
    tenant_id: UUID,
    item_id: UUID,
    city_ids: list[UUID] | None,
    from_: datetime | None,
    to_: datetime | None,
    agg: str,
) -> list[PriceBucketOut]:
    """Agrega por bucket de tempo e cidade. `1h` usa date_trunc('hour', ...);
    `24h` usa date_trunc('day', ...) — um bucket diário cobre a janela de 24h.

    Mesma semântica de `city_ids` de `query_raw_prices`: `None` = sem filtro,
    `[]` = filtro para cidades específicas que não resolveram para nenhum id.
    """
    bucket_unit = "hour" if agg == "1h" else "day"
    bucket_expr = func.date_trunc(bucket_unit, Price.collected_at).label("bucket_start")

    filters = [Price.tenant_id == tenant_id, Price.item_id == item_id]
    if city_ids is not None:
        filters.append(Price.city_id.in_(city_ids))
    if from_:
        filters.append(Price.collected_at >= from_)
    if to_:
        filters.append(Price.collected_at <= to_)

    stmt = (
        select(
            Price.city_id,
            bucket_expr,
            func.min(Price.sell_price_min).label("sell_min"),
            func.avg(Price.sell_price_min).label("sell_avg"),
            func.max(Price.sell_price_min).label("sell_max"),
            func.min(Price.buy_price_max).label("buy_min"),
            func.avg(Price.buy_price_max).label("buy_avg"),
            func.max(Price.buy_price_max).label("buy_max"),
            func.sum(Price.qty).label("qty_sum"),
        )
        .where(*filters)
        .group_by(Price.city_id, bucket_expr)
        .order_by(Price.city_id, bucket_expr.desc())
    )

    rows = db.execute(stmt).all()
    return [
        PriceBucketOut(
            city_id=row.city_id,
            bucket_start=row.bucket_start,
            sell_min=row.sell_min or 0,
            sell_avg=float(row.sell_avg or 0),
            sell_max=row.sell_max or 0,
            buy_min=row.buy_min or 0,
            buy_avg=float(row.buy_avg or 0),
            buy_max=row.buy_max or 0,
            qty_sum=row.qty_sum or 0,
        )
        for row in rows
    ]


def record_prices(db: Session, tenant_id: UUID, rows: list[dict]) -> list[Price]:
    """Insere snapshots de preço e invalida o cache dos itens afetados.

    TODO (fase 2): ligar isto ao worker como o "consumer" que lê o canal
    Redis `prices_updates` e persiste no Postgres — hoje é chamado só pelos
    testes de integração para popular dados.
    """
    created: list[Price] = []
    affected_items: set[UUID] = set()

    for row in rows:
        price = Price(
            tenant_id=tenant_id,
            item_id=row["item_id"],
            city_id=row["city_id"],
            sell_price_min=row.get("sell_price_min", 0),
            sell_price_max=row.get("sell_price_max", 0),
            buy_price_min=row.get("buy_price_min", 0),
            buy_price_max=row.get("buy_price_max", 0),
            quality=row.get("quality", 1),
            qty=row.get("qty", 0),
            collected_at=row.get("collected_at") or func.now(),
        )
        db.add(price)
        created.append(price)
        affected_items.add(row["item_id"])

    db.flush()
    for item_id in affected_items:
        invalidate_item_prices_cache(tenant_id, item_id)

    return created
