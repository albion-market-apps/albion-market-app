"""Coleta de preços na Albion Online Data Project.

TODO (fase 2): substituir o stub por uma chamada real a
`{ALBION_BASE_URL}/prices/{items}.json?locations={cities}` e persistir o
resultado na tabela `prices` (com RLS aplicado via SET LOCAL app.tenant_id).
"""

import json
import logging
import time
from dataclasses import dataclass

import httpx
import redis

from worker_app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_MAX_RETRIES = 3
_BACKOFF_SECONDS = 2.0


@dataclass
class PriceSnapshot:
    item: str
    city: str
    sell_price_min: int
    sell_price_max: int
    buy_price_min: int
    buy_price_max: int
    quality: int = 1


def fetch_prices(items: list[str], cities: list[str]) -> list[PriceSnapshot]:
    """Busca preços para `items` em `cities`. Faz backoff manual em falha de rede."""
    url = f"{settings.albion_base_url}/prices/{','.join(items)}.json"
    params = {"locations": ",".join(cities)}

    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return _parse_response(response.json())
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "falha ao buscar preços (tentativa %s/%s): %s", attempt, _MAX_RETRIES, exc
            )
            time.sleep(_BACKOFF_SECONDS * attempt)

    logger.error("desistindo após %s tentativas: %s", _MAX_RETRIES, last_error)
    return []


def _parse_response(payload: list[dict]) -> list[PriceSnapshot]:
    return [
        PriceSnapshot(
            item=row["item_id"],
            city=row["city"],
            sell_price_min=row.get("sell_price_min", 0),
            sell_price_max=row.get("sell_price_max", 0),
            buy_price_min=row.get("buy_price_min", 0),
            buy_price_max=row.get("buy_price_max", 0),
            quality=row.get("quality", 1),
        )
        for row in payload
    ]


def publish_updates(snapshots: list[PriceSnapshot]) -> None:
    """Publica os snapshots coletados no canal Redis `prices_updates`
    (placeholder para o front/worker de alertas).
    """
    client = redis.from_url(settings.redis_url)
    payload = json.dumps([snapshot.__dict__ for snapshot in snapshots])
    client.publish("prices_updates", payload)
