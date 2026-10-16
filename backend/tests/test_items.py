from fastapi.testclient import TestClient

from tests.conftest import TENANT_A


def _headers() -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def test_search_by_exact_code_ranks_first(client: TestClient, world: dict) -> None:
    response = client.get("/items", params={"query": "ITEM_A"}, headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["items"][0]["code"] == "ITEM_A"


def test_search_by_alias_finds_item(client: TestClient, world: dict) -> None:
    response = client.get("/items", params={"query": "alias-a"}, headers=_headers())
    assert response.status_code == 200
    body = response.json()
    codes = [item["code"] for item in body["items"]]
    assert "ITEM_A" in codes


def test_search_no_match_returns_empty(client: TestClient, world: dict) -> None:
    response = client.get("/items", params={"query": "item-que-nao-existe-xyz"}, headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_pagination_respects_page_size(client: TestClient, world: dict) -> None:
    response = client.get("/items", params={"page": 1, "page_size": 1}, headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) <= 1
    assert body["total"] >= 1
