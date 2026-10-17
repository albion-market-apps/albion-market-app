"""Comparação simples entre matéria-prima e material refinado correspondente
— **sem calcular lucro de refino** (decisão explícita do usuário: a taxa de
retorno do refino depende de foco, especialização de cidade e premium,
nada disso dá pra saber pela API de preços — ver docs/claude.md, turno 13).
Só mostra o preço da matéria-prima na cidade informada ao lado do melhor
preço de venda **instantânea, já líquido da taxa de 8%** do material
refinado (mesma taxa confirmada com print real do jogo, turno 16 — ver
`app.services.opportunities`), pra pessoa fazer a própria conta do refino
em cima de um valor que já é o que ela receberia de verdade.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.services.opportunities import latest_quality1_prices, net_instant_sell_price

# (sufixo da matéria-prima, sufixo do material refinado) — mesma convenção
# de code usada no resto do catálogo (T{tier}_{sufixo}).
RESOURCE_PAIRS = [
    ("ORE", "METALBAR"),
    ("WOOD", "PLANKS"),
    ("HIDE", "LEATHER"),
    ("FIBER", "CLOTH"),
    ("ROCK", "STONEBLOCK"),
]
RESOURCE_TIERS = range(2, 9)  # T2..T8


@dataclass
class RefiningComparison:
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


def refining_comparison_at_city(
    db: Session, tenant_id: UUID, origin_city_id: UUID
) -> list[RefiningComparison]:
    """Pra cada par matéria-prima/refinado (todas as tiers 2-8) que existir
    no catálogo do tenant: preço de compra da matéria-prima em
    `origin_city_id` (ignorado se não houver oferta ali — nada pra comprar,
    nada pra mostrar) e melhor oferta de compra do material refinado entre
    todas as cidades."""
    items = list(db.scalars(select(Item).where(Item.tenant_id == tenant_id)))
    item_by_code = {item.code: item for item in items}

    pairs: list[tuple[Item, Item]] = []
    for tier in RESOURCE_TIERS:
        for raw_suffix, refined_suffix in RESOURCE_PAIRS:
            raw_item = item_by_code.get(f"T{tier}_{raw_suffix}")
            refined_item = item_by_code.get(f"T{tier}_{refined_suffix}")
            if raw_item is not None and refined_item is not None:
                pairs.append((raw_item, refined_item))

    if not pairs:
        return []

    all_ids = [item.id for pair in pairs for item in pair]
    prices = latest_quality1_prices(db, tenant_id, all_ids)

    results: list[RefiningComparison] = []
    for raw_item, refined_item in pairs:
        raw_entry = prices.get(raw_item.id, {}).get(origin_city_id)
        if raw_entry is None or raw_entry["sell_price_min"] <= 0:
            continue  # nada à venda dessa matéria-prima na cidade informada

        sellable = {
            city_id: entry
            for city_id, entry in prices.get(refined_item.id, {}).items()
            if entry["buy_price_max"] > 0
        }
        if not sellable:
            continue  # material refinado sem nenhuma oferta de compra em lugar nenhum

        best_city_id = max(sellable, key=lambda city_id: sellable[city_id]["buy_price_max"])

        results.append(
            RefiningComparison(
                tier=raw_item.tier,
                raw_item_id=raw_item.id,
                raw_code=raw_item.code,
                raw_name=raw_item.name,
                raw_price=raw_entry["sell_price_min"],
                refined_item_id=refined_item.id,
                refined_code=refined_item.code,
                refined_name=refined_item.name,
                refined_best_price=net_instant_sell_price(sellable[best_city_id]["buy_price_max"]),
                refined_best_city_id=best_city_id,
            )
        )

    results.sort(key=lambda row: row.tier)
    return results
