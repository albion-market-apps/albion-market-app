from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TENANT_A, seed_prices


def _headers() -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def test_raw_prices_returns_latest_records_per_city(
    client: TestClient, db: Session, world: dict
) -> None:
    seed_prices(db, TENANT_A, world["item_a"], world["city_a"], count=5)
    seed_prices(db, TENANT_A, world["item_a"], world["city_a2"], count=3)

    response = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "raw"},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agg"] == "raw"
    assert len(body["data"]) == 8  # 5 da city_a + 3 da city_a2

    city_ids_in_response = {row["city_id"] for row in body["data"]}
    assert str(world["city_a"]) in city_ids_in_response
    assert str(world["city_a2"]) in city_ids_in_response


def test_raw_prices_filters_by_cities_param(client: TestClient, db: Session, world: dict) -> None:
    seed_prices(db, TENANT_A, world["item_a"], world["city_a"], count=2)
    seed_prices(db, TENANT_A, world["item_a"], world["city_a2"], count=2)

    response = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "raw", "cities": "city-a"},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert all(row["city_id"] == str(world["city_a"]) for row in body["data"])


def test_hourly_aggregation_buckets_and_sums_qty(
    client: TestClient, db: Session, world: dict
) -> None:
    now = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
    # dois pontos na mesma hora (bucket único) com qty 5 e 6 => soma 11
    seed_prices(
        db,
        TENANT_A,
        world["item_a"],
        world["city_a"],
        count=2,
        start=now,
        step=timedelta(minutes=5),
        sell_price_min=100,
    )

    response = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "1h", "cities": "city-a"},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agg"] == "1h"
    assert len(body["data"]) == 1

    bucket = body["data"][0]
    assert bucket["city_id"] == str(world["city_a"])
    assert bucket["qty_sum"] == 5 + 6  # qty dos dois pontos seedados (5+i)
    assert bucket["sell_min"] == 100
    assert bucket["sell_max"] == 101


def test_invalid_agg_returns_422(client: TestClient, world: dict) -> None:
    response = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "weekly"},
        headers=_headers(),
    )
    assert response.status_code == 422
