"""Cálculo de oportunidade de arbitragem: comprar um item barato numa
cidade (`sell_price_min` — preço de compra instantânea, sem taxa pro
comprador) e vender caro em outra.

A venda tem **dois números**, os dois já líquidos de taxa (confirmado
pelo usuário com print real do cliente do jogo, turno 16 — "Vara de Pescar
do Perito" em Lymhurst: venda instantânea de 1.345 cobrou 108 de taxa
(8,0%); pedido de venda de 3.880 cobrou 310 de taxa (8,0%) + 97 de "Taxa de
Ordem" (2,5%), essa paga na hora de criar o pedido, **mesmo que ele nunca
venda**):
- venda instantânea (`sell_price`): preencher a melhor ordem de compra já
  publicada ali, na hora — líquido de `SALES_TAX_RATE` (8%).
- venda por ordem própria (`sell_order_price`): listar ao preço da oferta
  de venda mais barata já publicada ali (pra ser competitivo) e esperar
  vender — líquido de `SALES_TAX_RATE` **e** de `ORDER_SETUP_FEE_RATE`
  (2,5%, cobrada ao criar o pedido, não só se vender). Normalmente bem
  maior que a venda instantânea (o exemplo real deu quase 3x), mas não é
  garantido: pode demorar, pode nunca vender, pode ser atropelado por
  outra ordem mais barata.

Taxas assumem conta **sem Premium** (Premium paga metade — o jogo mostra
isso na própria tela de venda). Não dá pra saber pela API se o usuário tem
Premium, então assumimos o cenário mais conservador (taxa cheia).

O **lucro/ranking continua baseado só na venda instantânea** (o cenário
garantido, sem espera) — `sell_order_price` é só informação extra pro
usuário decidir, não entra no cálculo de lucro usado pra ordenar o ranking.

Sempre usa o preço de qualidade 1 ("Normal") como referência — mesma
decisão tomada em `web/src/lib/api.ts` pro front não misturar qualidades
diferentes numa mesma comparação (ver docs/claude.md, turno 11/12).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.price import Price

SALES_TAX_RATE = 0.08
ORDER_SETUP_FEE_RATE = 0.025


def net_instant_sell_price(gross_buy_price_max: int) -> int:
    """Quanto você recebe vendendo instantaneamente (preenchendo a melhor
    ordem de compra já publicada) — só desconta `SALES_TAX_RATE`."""
    return round(gross_buy_price_max * (1 - SALES_TAX_RATE))


def net_sell_order_price(gross_sell_price_min: int) -> int:
    """Quanto você recebe **se** o seu próprio pedido de venda (criado no
    preço da oferta mais barata já publicada, pra ser competitivo) vender —
    desconta `SALES_TAX_RATE` + `ORDER_SETUP_FEE_RATE`. A taxa de ordem é
    paga na criação do pedido, então esse número já assume que ele vendeu;
    se nunca vender, a taxa de ordem ainda assim já foi perdida."""
    return round(gross_sell_price_min * (1 - SALES_TAX_RATE - ORDER_SETUP_FEE_RATE))


def latest_quality1_prices(
    db: Session, tenant_id: UUID, item_ids: list[UUID] | None = None
) -> dict[UUID, dict[UUID, dict]]:
    """Preço mais recente (qualidade 1) por (item, cidade).

    Retorna `{item_id: {city_id: {sell_price_min, buy_price_max, collected_at}}}`.
    """
    filters = [Price.tenant_id == tenant_id, Price.quality == 1]
    if item_ids is not None:
        filters.append(Price.item_id.in_(item_ids))

    rn = (
        func.row_number()
        .over(partition_by=[Price.item_id, Price.city_id], order_by=Price.collected_at.desc())
        .label("rn")
    )
    ranked = (
        select(
            Price.item_id,
            Price.city_id,
            Price.sell_price_min,
            Price.buy_price_max,
            Price.collected_at,
            rn,
        )
        .where(*filters)
        .cte("ranked_quality1")
    )
    rows = db.execute(select(ranked).where(ranked.c.rn == 1)).all()

    result: dict[UUID, dict[UUID, dict]] = {}
    for row in rows:
        result.setdefault(row.item_id, {})[row.city_id] = {
            "sell_price_min": row.sell_price_min,
            "buy_price_max": row.buy_price_max,
            "collected_at": row.collected_at,
        }
    return result


@dataclass
class TradeOpportunity:
    item_id: UUID
    buy_city_id: UUID
    buy_price: int
    sell_city_id: UUID
    sell_price: int  # venda instantânea (buy_price_max) — usado no lucro/ranking
    sell_order_price: int  # venda por ordem própria (sell_price_min da cidade de venda) — só informativo
    profit: int
    collected_at: datetime


def best_trade_for_item(
    item_id: UUID,
    prices_by_city: dict[UUID, dict],
    origin_city_id: UUID | None,
) -> TradeOpportunity | None:
    """Melhor par (cidade de compra, cidade de venda) pra um item — sempre
    cidades **diferentes**: comprar e "vender" na mesma cidade não é
    arbitragem nenhuma (se não tem viagem, não tem razão nenhuma pra tratar
    compra e venda como lugares separados — e normalmente dá prejuízo
    garantido, porque `buy_price_max` de uma cidade é tipicamente menor que
    o próprio `sell_price_min` dela, por causa do spread do mercado).

    `origin_city_id=None` deixa a cidade de compra livre (testa todas as
    combinações possíveis) — usado na lista de favoritos. Com
    `origin_city_id` definido, a compra é travada naquela cidade (o
    usuário já disse onde está) — usado em "melhor item pra comprar daqui".
    Busca exaustiva sobre todos os pares (compra, venda) — o catálogo de
    cidades é pequeno (7), então O(n²) é barato e evita o erro de escolher
    a melhor cidade de compra e a melhor de venda de forma independente
    (que pode "empatar" na mesma cidade mesmo quando outra combinação daria
    mais lucro, ou pior, mais prejuízo). Cidades sem oferta de compra/venda
    (`== 0`, ver `app.services.collector`: zero significa "sem dado", não
    preço real) são ignoradas dos dois lados.
    """
    buyable = {c: p for c, p in prices_by_city.items() if p["sell_price_min"] > 0}
    sellable = {c: p for c, p in prices_by_city.items() if p["buy_price_max"] > 0}

    if origin_city_id is not None:
        if origin_city_id not in buyable:
            return None
        buy_candidates = {origin_city_id: buyable[origin_city_id]}
    else:
        buy_candidates = buyable

    best: TradeOpportunity | None = None
    for buy_city_id, buy_entry in buy_candidates.items():
        for sell_city_id, sell_entry in sellable.items():
            if sell_city_id == buy_city_id:
                continue
            buy_price = buy_entry["sell_price_min"]
            sell_price = net_instant_sell_price(sell_entry["buy_price_max"])
            sell_order_price = (
                net_sell_order_price(sell_entry["sell_price_min"])
                if sell_entry["sell_price_min"] > 0
                else 0
            )
            profit = sell_price - buy_price
            if best is None or profit > best.profit:
                best = TradeOpportunity(
                    item_id=item_id,
                    buy_city_id=buy_city_id,
                    buy_price=buy_price,
                    sell_city_id=sell_city_id,
                    sell_price=sell_price,
                    sell_order_price=sell_order_price,
                    profit=profit,
                    collected_at=max(buy_entry["collected_at"], sell_entry["collected_at"]),
                )
    return best


def best_trades_for_items(
    db: Session, tenant_id: UUID, item_ids: list[UUID], origin_city_id: UUID | None = None
) -> list[TradeOpportunity]:
    """Uma oportunidade por item pedido (favoritos) — itens sem preço
    coletado ainda, ou sem combinação compra/venda válida, ficam de fora
    (não entram como `None` na lista; o caller decide como sinalizar
    "sem dado" pros item_ids que não vieram de volta)."""
    prices = latest_quality1_prices(db, tenant_id, item_ids)
    opportunities = []
    for item_id in item_ids:
        trade = best_trade_for_item(item_id, prices.get(item_id, {}), origin_city_id)
        if trade is not None:
            opportunities.append(trade)
    return opportunities


def _rank_opportunities(
    db: Session, tenant_id: UUID, origin_city_id: UUID | None, limit: int
) -> list[TradeOpportunity]:
    prices = latest_quality1_prices(db, tenant_id)
    opportunities = []
    for item_id, prices_by_city in prices.items():
        trade = best_trade_for_item(item_id, prices_by_city, origin_city_id)
        if trade is not None and trade.profit > 0:
            opportunities.append(trade)
    opportunities.sort(key=lambda trade: trade.profit, reverse=True)
    return opportunities[:limit]


def best_trades_from_city(
    db: Session, tenant_id: UUID, origin_city_id: UUID, limit: int = 5
) -> list[TradeOpportunity]:
    """Ranking dos itens mais lucrativos pra comprar em `origin_city_id`
    agora e vender em outra cidade — todo o catálogo do tenant com preço
    coletado, ordenado por lucro decrescente."""
    return _rank_opportunities(db, tenant_id, origin_city_id, limit)


def best_trades_global(db: Session, tenant_id: UUID, limit: int = 5) -> list[TradeOpportunity]:
    """Ranking dos itens mais lucrativos do catálogo inteiro, cidade de
    compra e de venda livres (sem travar "onde você está") — calculado na
    hora a partir do preço mais recente que o coletor já trouxe (a cada
    ~5min, ver `POLL_INTERVAL_SECONDS`), não uma lista pré-calculada e
    cacheada por hora: o catálogo é pequeno o bastante (algumas centenas de
    itens × até 7 cidades) pra isso custar bem menos que 1s, então não tem
    motivo pra servir um dado mais velho do que o necessário."""
    return _rank_opportunities(db, tenant_id, None, limit)
