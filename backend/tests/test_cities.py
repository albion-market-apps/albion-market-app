from fastapi.testclient import TestClient

from tests.conftest import TENANT_A, TENANT_B


def _headers(tenant_id) -> dict[str, str]:
    return {"X-Tenant-ID": str(tenant_id)}


def test_list_cities_returns_only_tenant_own_cities(client: TestClient, world: dict) -> None:
    response = client.get("/cities", headers=_headers(TENANT_A))
    assert response.status_code == 200
    body = response.json()
    codes = {city["code"] for city in body}
    assert codes == {"city-a", "city-a2"}


def test_list_cities_respects_rls_across_tenants(client: TestClient, world: dict) -> None:
    response = client.get("/cities", headers=_headers(TENANT_B))
    assert response.status_code == 200
    body = response.json()
    codes = {city["code"] for city in body}
    assert codes == {"city-b"}
