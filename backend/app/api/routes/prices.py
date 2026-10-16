from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache import build_prices_cache_key, get_cached_json, set_cached_json
from app.db.rls import get_current_tenant_id, get_tenant_db
from app.schemas.prices import PriceBucketOut, PriceRawOut, PricesResponse
from app.services.pricing import query_aggregated_prices, query_raw_prices, resolve_city_ids

router = APIRouter(prefix="/prices", tags=["prices"])

VALID_AGGS = {"raw", "1h", "24h"}


@router.get("", response_model=PricesResponse)
def list_prices(
    item_id: UUID = Query(...),
    cities: str | None = Query(default=None, description="códigos de cidade separados por vírgula"),
    from_: datetime | None = Query(default=None, alias="from"),
    to_: datetime | None = Query(default=None, alias="to"),
    agg: str = Query(default="raw"),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> PricesResponse:
    if agg not in VALID_AGGS:
        raise HTTPException(
            status_code=422, detail=f"agg inválido: {agg!r}. Use um de {sorted(VALID_AGGS)}."
        )

    # None = sem filtro de cidade (todas); lista (mesmo vazia) = filtro explícito.
    # Lista vazia acontece quando `cities` foi passado mas nenhum código bateu com
    # nenhuma cidade do tenant — o resultado tem que ser vazio, não "ignora o
    # filtro e devolve tudo" (ver nota em app.services.pricing.query_raw_prices).
    city_codes = [c.strip() for c in cities.split(",") if c.strip()] if cities else []
    city_ids: list[UUID] | None = (
        resolve_city_ids(db, tenant_id, city_codes) if city_codes else None
    )

    cache_key = build_prices_cache_key(
        tenant_id,
        item_id,
        city_ids or [],
        agg,
        from_.isoformat() if from_ else None,
        to_.isoformat() if to_ else None,
    )
    cached = get_cached_json(cache_key)
    if cached is not None:
        return PricesResponse.model_validate(cached)

    if agg == "raw":
        data: list[PriceRawOut] | list[PriceBucketOut] = query_raw_prices(
            db, tenant_id, item_id, city_ids, from_, to_
        )
    else:
        data = query_aggregated_prices(db, tenant_id, item_id, city_ids, from_, to_, agg)

    response = PricesResponse(item_id=item_id, agg=agg, data=data)
    set_cached_json(cache_key, response.model_dump(mode="json"))
    return response
