from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
    assert trade["sell_price"] == 890
    assert trade["profit"] == 790


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
    assert body[0]["profit"] == 790


def test_best_from_city_excludes_negative_profit(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_cheap_and_expensive_city(db, world)

    # Comprar na cidade cara (city_a2) e vender na melhor oferta do mercado
    # (também city_a2, 890) dá prejuízo (900 > 890) — não deve aparecer.
    response = client.get(
        "/opportunities/best-from-city",
        params={"city_id": str(world["city_a2"])},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == []
