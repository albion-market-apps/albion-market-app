from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.rls import set_tenant
from app.models.item import Item
from tests.conftest import TENANT_A, seed_prices


def _headers() -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def _seed_resource_pair(db: Session, world: dict) -> None:
    with db.begin():
        set_tenant(db, str(TENANT_A))
        raw = Item(tenant_id=TENANT_A, code="T4_ORE", name="Minério de Ferro", tier=4, enchant=0)
        refined = Item(
            tenant_id=TENANT_A, code="T4_METALBAR", name="Barra de Metal", tier=4, enchant=0
        )
        db.add_all([raw, refined])
        db.flush()
        world["raw_ore"] = raw.id
        world["refined_metalbar"] = refined.id

    # matéria-prima à venda na city_a; material refinado com melhor oferta na city_a2.
    seed_prices(db, TENANT_A, world["raw_ore"], world["city_a"], count=1, sell_price_min=50)
    seed_prices(db, TENANT_A, world["refined_metalbar"], world["city_a2"], count=1, sell_price_min=300)


def test_refining_pairs_raw_at_city_with_best_refined_sell(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_resource_pair(db, world)

    response = client.get(
        "/refining", params={"city_id": str(world["city_a"])}, headers=_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["tier"] == 4
    assert row["raw_code"] == "T4_ORE"
    assert row["raw_price"] == 50
    assert row["refined_code"] == "T4_METALBAR"
    assert row["refined_best_city_id"] == str(world["city_a2"])
    # buy_price_max do seed = sell_price_min - 10 + i = 300 - 10 + 0 = 290
    assert row["refined_best_price"] == 290


def test_refining_empty_when_no_raw_offer_at_city(
    client: TestClient, db: Session, world: dict
) -> None:
    _seed_resource_pair(db, world)

    # city_a2 não tem oferta de T4_ORE — nada pra comprar ali.
    response = client.get(
        "/refining", params={"city_id": str(world["city_a2"])}, headers=_headers()
    )
    assert response.status_code == 200
    assert response.json() == []


def test_refining_no_pairs_in_catalog_returns_empty(client: TestClient, world: dict) -> None:
    response = client.get(
        "/refining", params={"city_id": str(world["city_a"])}, headers=_headers()
    )
    assert response.status_code == 200
    assert response.json() == []
