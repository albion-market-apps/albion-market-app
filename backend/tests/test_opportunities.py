from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.rls import set_tenant
from app.services.pricing import record_prices
from tests.conftest import TENANT_A, seed_prices


def _headers() -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def _seed_cheap_and_expensive_city(db: Session, world: dict) -> None:
    # city_a: barata pra comprar (sell_price_min=100); city_a2: boa pra vender
    # (buy_price_max alto, pois sell_price_min=900 => buy_price_max=890).
    seed_prices(db, TENANT_A, world["item_a"], world["city_a"], count=1, sell_price_min=100)
    seed_prices(db, TENANT_A, world["item_a"], world["city_a2"], count=1, sell_price_min=900)


def test_favorites_finds_best_buy_and_sell_city(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_cheap_and_expensive_city(db, world)

    response = client.get(
        "/opportunities/favorites",
        params={"item_ids": str(world["item_a"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    trade = body[0]
    assert trade["buy_city_id"] == str(world["city_a"])
    assert trade["buy_price"] == 100
    assert trade["sell_city_id"] == str(world["city_a2"])
    # buy_price_max bruto de city_a2 = 890; líquido de venda instantânea
    # (8% de taxa) = round(890 * 0.92) = 819.
    assert trade["sell_price"] == 819
    assert trade["profit"] == 719
    # sell_order_price = líquido de pedido de venda no sell_price_min bruto
    # de city_a2 (900): round(900 * (1 - 0.08 - 0.025)) = 806.
    assert trade["sell_order_price"] == 806


def test_favorites_rejects_more_than_four_items(client: TestClient, world: dict) -> None:
    fake_ids = ",".join(
        [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
            "44444444-4444-4444-4444-444444444444",
            "55555555-5555-5555-5555-555555555555",
        ]
    )
    response = client.get(
        "/opportunities/favorites", params={"item_ids": fake_ids}, headers=_headers()
    )
    assert response.status_code == 422


def test_favorites_skips_items_without_price_data(client: TestClient, world: dict) -> None:
    response = client.get(
        "/opportunities/favorites",
        params={"item_ids": str(world["item_a"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_best_from_city_ranks_by_profit_and_locks_buy_city(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_cheap_and_expensive_city(db, world)

    response = client.get(
        "/opportunities/best-from-city",
        params={"city_id": str(world["city_a"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["buy_city_id"] == str(world["city_a"])
    assert body[0]["profit"] == 719


def test_best_from_city_excludes_negative_profit(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_cheap_and_expensive_city(db, world)

    # Comprar na cidade cara (city_a2, 900) só pode vender na outra cidade
    # (city_a, buy_price_max=90 — vender em city_a2 de novo não vale, ver
    # test_best_trade_never_buys_and_sells_in_the_same_city) — 90 < 900,
    # prejuízo garantido, não deve aparecer.
    response = client.get(
        "/opportunities/best-from-city",
        params={"city_id": str(world["city_a2"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_best_trade_never_buys_and_sells_in_the_same_city(
    client: TestClient, db: Session, world: dict
) -> None:
    """Bug real reportado pelo usuário (turno 14): uma cidade que tem ao
    mesmo tempo o menor `sell_price_min` E o maior `buy_price_max` virava
    "compre e venda aqui mesmo" — sem viagem nenhuma, isso não é
    arbitragem, só prejuízo (ou um "lucro" bobo) disfarçado de
    oportunidade. `city_a` tem os dois extremos de propósito; a combinação
    correta precisa ignorar essa coincidência e escolher o melhor par entre
    cidades DIFERENTES."""
    now = datetime.now(UTC)
    with db.begin():
        set_tenant(db, str(TENANT_A))
        record_prices(
            db,
            TENANT_A,
            [
                {
                    "item_id": world["item_a"],
                    "city_id": world["city_a"],
                    "sell_price_min": 100,  # a mais barata pra comprar...
                    "sell_price_max": 110,
                    "buy_price_min": 180,
                    "buy_price_max": 200,  # ...e também a melhor oferta de compra
                    "quality": 1,
                    "qty": 0,
                    "collected_at": now,
                },
                {
                    "item_id": world["item_a"],
                    "city_id": world["city_a2"],
                    "sell_price_min": 150,
                    "sell_price_max": 160,
                    "buy_price_min": 40,
                    "buy_price_max": 50,
                    "quality": 1,
                    "qty": 0,
                    "collected_at": now,
                },
            ],
        )

    response = client.get(
        "/opportunities/favorites",
        params={"item_ids": str(world["item_a"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    trade = body[0]
    # city_a sozinha "pareceria" perfeita (compre a 100, venda a 200) — mas
    # é a MESMA cidade pros dois lados, não vale. A melhor combinação real
    # entre cidades diferentes é comprar em city_a2 (150) e vender em
    # city_a: líquido de taxa (8%) = round(200 * 0.92) = 184, lucro 34 —
    # bem menor que o "lucro" sem sentido que o bug mostraria.
    assert trade["buy_city_id"] == str(world["city_a2"])
    assert trade["buy_price"] == 150
    assert trade["sell_city_id"] == str(world["city_a"])
    assert trade["sell_price"] == 184
    assert trade["profit"] == 34


def test_top_opportunities_ranks_whole_catalog_without_city_filter(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_cheap_and_expensive_city(db, world)

    response = client.get("/opportunities/top", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["buy_city_id"] == str(world["city_a"])
    assert body[0]["sell_city_id"] == str(world["city_a2"])
    assert body[0]["profit"] == 719


def test_top_opportunities_respects_limit(client: TestClient, db: Session, world: dict) -> None:
    _seed_cheap_and_expensive_city(db, world)

    response = client.get("/opportunities/top", params={"limit": 0}, headers=_headers())
    # limit tem ge=1 no schema — 0 é inválido, não "nenhum resultado".
    assert response.status_code == 422
