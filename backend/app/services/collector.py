"""Coleta de preços reais na Albion Online Data Project (AODP) e persistência
no Postgres, para todo o catálogo de itens/cidades do tenant.

Roda **dentro do processo da API** (ver `app.main`, lifespan), não como
worker separado — decisão forçada pelo Render free tier não ter plano
gratuito de Background Worker (ver docs/claude.md, changelog turno 11).
`worker/` continua existindo pra Docker Compose local, mas em produção é
este módulo que alimenta a tabela `prices`.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.rls import set_tenant
from app.db.session import SessionLocal
from app.models.city import City
from app.models.item import Item
from app.services.pricing import record_prices

logger = logging.getLogger(__name__)
settings = get_settings()

# A AODP não documenta um limite oficial de itens por requisição, mas pedir
# centenas de uma vez de uma vez só é um jeito conhecido de tomar timeout ou
# 400 nas ferramentas da comunidade — depois do catálogo crescer de 20 pra
# 160 itens (turno 13), passamos a pedir em lotes.
_AODP_BATCH_SIZE = 50


def _unique_name(item: Item) -> str:
    """Reconstrói o `unique_name` que a AODP espera: `code` puro pra enchant 0,
    `code@enchant` pros níveis encantados (convenção do próprio jogo)."""
    return item.code if item.enchant == 0 else f"{item.code}@{item.enchant}"


def _fetch_aodp_prices_batch(unique_names: list[str], city_codes: list[str]) -> list[dict]:
    url = f"{settings.albion_base_url}/prices/{','.join(unique_names)}.json"
    response = httpx.get(url, params={"locations": ",".join(city_codes)}, timeout=20.0)
    response.raise_for_status()
    return response.json()


def _fetch_aodp_prices(unique_names: list[str], city_codes: list[str]) -> list[dict]:
    """Busca em lotes de `_AODP_BATCH_SIZE` itens — um lote que falhar (rede,
    timeout) só perde aquele pedaço do catálogo neste ciclo, não a coleta
    inteira; o próximo ciclo tenta de novo."""
    payload: list[dict] = []
    for start in range(0, len(unique_names), _AODP_BATCH_SIZE):
        batch = unique_names[start : start + _AODP_BATCH_SIZE]
        try:
            payload.extend(_fetch_aodp_prices_batch(batch, city_codes))
        except httpx.HTTPError:
            logger.exception("coletor: falha buscando lote de %s itens na AODP", len(batch))
    return payload


def collect_once(tenant_id: UUID) -> int:
    """Busca preços reais de todo o catálogo do tenant e grava no Postgres.

    Ignora linhas em que a AODP não tem nenhuma oferta pro par item/cidade
    (`sell_price_min == 0 and buy_price_max == 0`) — gravar zero faria uma
    "falta de dado" parecer um preço real de 0, o que quebraria a
    comparação entre cidades. Retorna quantas linhas foram gravadas.
    """
    db = SessionLocal()
    try:
        with db.begin():
            set_tenant(db, str(tenant_id))
            items = list(db.scalars(select(Item).where(Item.tenant_id == tenant_id)))
            cities = list(db.scalars(select(City).where(City.tenant_id == tenant_id)))
            if not items or not cities:
                return 0

            item_by_unique_name = {_unique_name(item): item for item in items}
            city_by_code = {city.code: city for city in cities}

            payload = _fetch_aodp_prices(
                list(item_by_unique_name.keys()), list(city_by_code.keys())
            )

            now = datetime.now(UTC)
            rows = []
            for entry in payload:
                item = item_by_unique_name.get(entry.get("item_id", ""))
                city = city_by_code.get(entry.get("city", ""))
                sell_min = entry.get("sell_price_min", 0)
                buy_max = entry.get("buy_price_max", 0)
                if item is None or city is None or (sell_min == 0 and buy_max == 0):
                    continue
                rows.append(
                    {
                        "item_id": item.id,
                        "city_id": city.id,
                        "sell_price_min": sell_min,
                        "sell_price_max": entry.get("sell_price_max", 0),
                        "buy_price_min": entry.get("buy_price_min", 0),
                        "buy_price_max": buy_max,
                        "quality": entry.get("quality", 1),
                        "qty": 0,
                        "collected_at": now,
                    }
                )

            record_prices(db, tenant_id, rows)
            logger.info("coletor: %s linhas de preço gravadas", len(rows))
            return len(rows)
    finally:
        db.close()
