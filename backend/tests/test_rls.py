from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TENANT_A, TENANT_B, seed_prices


def test_items_from_other_tenant_are_not_returned(client: TestClient, world: dict) -> None:
    response = client.get(
        "/items", params={"query": "ITEM_"}, headers={"X-Tenant-ID": str(TENANT_A)}
    )
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["items"]}

    assert "ITEM_A" in codes
    assert "ITEM_B" not in codes  # RLS: tenant A nunca vê itens do tenant B


def test_prices_from_other_tenant_are_not_returned(
    client: TestClient, db: Session, world: dict
) -> None:
    seed_prices(db, TENANT_A, world["item_a"], world["city_a"], count=2)
    seed_prices(db, TENANT_B, world["item_b"], world["city_b"], count=2)

    # tenant B busca preços do PRÓPRIO item_id — não deve ver nada mesmo que
    # (por engano) alguém tente consultar o item_id do tenant A.
    response = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "raw"},
        headers={"X-Tenant-ID": str(TENANT_B)},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []  # RLS filtra: item_a pertence ao tenant A, não ao B


def test_same_item_id_different_tenant_sees_only_own_data(
    client: TestClient, db: Session, world: dict
) -> None:
    seed_prices(db, TENANT_A, world["item_a"], world["city_a"], count=3)

    response_a = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "raw"},
        headers={"X-Tenant-ID": str(TENANT_A)},
    )
    response_b = client.get(
        "/prices",
        params={"item_id": str(world["item_a"]), "agg": "raw"},
        headers={"X-Tenant-ID": str(TENANT_B)},
    )

    assert len(response_a.json()["data"]) == 3
    assert response_b.json()["data"] == []
