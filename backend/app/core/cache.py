"""Cache de 5 minutos para GET /prices, com invalidação por prefixo.

Chave determinística: tenant:{tenant_id}:prices:{item_id}:{cities_hash}:{agg}:{from}:{to}
`cities_hash` é um hash curto da lista de city_ids ordenada (mantém a chave
curta e estável independente da ordem em que as cidades foram passadas).

Invalidação: ao gravar preços novos (ver `app.services.pricing.record_prices`),
removemos todas as chaves de cache daquele item (`tenant:{tenant_id}:prices:{item_id}:*`)
via SCAN + DELETE e publicamos um evento no canal `CACHE_INVALIDATED_CHANNEL`
para outros processos/instâncias que eventualmente mantenham cache próprio.
"""

import hashlib
import json
from functools import lru_cache
from uuid import UUID

import redis

from app.core.config import get_settings

PRICES_CACHE_TTL_SECONDS = 5 * 60
CACHE_INVALIDATED_CHANNEL = "prices:cache_invalidated"


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _cities_hash(city_ids: list[UUID]) -> str:
    joined = ",".join(sorted(str(c) for c in city_ids))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def build_prices_cache_key(
    tenant_id: UUID,
    item_id: UUID,
    city_ids: list[UUID],
    agg: str,
    from_: str | None,
    to_: str | None,
) -> str:
    return (
        f"tenant:{tenant_id}:prices:{item_id}:{_cities_hash(city_ids)}:"
        f"{agg}:{from_ or '-'}:{to_ or '-'}"
    )


def get_cached_json(key: str) -> dict | list | None:
    raw = get_redis().get(key)
    if raw is None:
        return None
    return json.loads(raw)


def set_cached_json(key: str, value: dict | list, ttl: int = PRICES_CACHE_TTL_SECONDS) -> None:
    get_redis().set(key, json.dumps(value, default=str), ex=ttl)


def invalidate_item_prices_cache(tenant_id: UUID, item_id: UUID) -> None:
    """Remove do cache todas as combinações de cidades/agg/janela para este item."""
    client = get_redis()
    pattern = f"tenant:{tenant_id}:prices:{item_id}:*"
    keys = list(client.scan_iter(match=pattern, count=200))
    if keys:
        client.delete(*keys)
    client.publish(
        CACHE_INVALIDATED_CHANNEL,
        json.dumps({"tenant_id": str(tenant_id), "item_id": str(item_id)}),
    )
