"""Fixtures de integração.

Exigem um Postgres real (com a extensão pgcrypto e as migrações da Alembic já
aplicadas — ver `make test-api` / `infra/docker-compose.yml`) porque a RLS
depende de `current_setting('app.tenant_id')`, que não existe em SQLite nem em
mocks. Dados de fixture são **commitados** (não só abertos em transação) para
que a API — que abre sua própria conexão por request — consiga vê-los, e são
limpos no teardown de cada teste.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.rls import set_tenant
from app.db.session import SessionLocal
from app.main import app
from app.models.city import City
from app.models.item import Item, ItemAlias
from app.models.tenant import Tenant
from app.services.pricing import record_prices

# Importante: NUNCA usar o mesmo UUID do TENANT_DEFAULT_ID (seed) aqui — o
# teardown desta fixture faz DELETE por tenant_id, e já aconteceu de apagar o
# catálogo semeado por engano quando os dois coincidiam.
TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _ensure_tenant(db: Session, tenant_id: uuid.UUID) -> None:
    if not db.get(Tenant, tenant_id):
        db.add(Tenant(id=tenant_id, name=f"Tenant {tenant_id}", slug=f"tenant-{tenant_id.hex[:8]}"))
        db.flush()


@pytest.fixture
def world(db: Session) -> Generator[dict[str, Any], None, None]:
    """Cria, para TENANT_A e TENANT_B, uma cidade e um item próprios — base para
    os testes de busca/preço e para o teste de isolamento por RLS.
    """
    created: dict[str, Any] = {}

    for tenant_id, label in ((TENANT_A, "a"), (TENANT_B, "b")):
        with db.begin():
            set_tenant(db, str(tenant_id))
            _ensure_tenant(db, tenant_id)

            city = City(tenant_id=tenant_id, code=f"city-{label}", name=f"City {label.upper()}")
            db.add(city)
            db.flush()

            item = Item(
                tenant_id=tenant_id,
                code=f"ITEM_{label.upper()}",
                name=f"Item {label.upper()}",
                tier=4,
                enchant=0,
            )
            db.add(item)
            db.flush()

            db.add(ItemAlias(tenant_id=tenant_id, item_id=item.id, alias=f"alias-{label}"))

            created[f"city_{label}"] = city.id
            created[f"item_{label}"] = item.id
            created[f"tenant_{label}"] = tenant_id

            if label == "a":
                # segunda cidade só no tenant A, para testar /prices com múltiplas cidades.
                city_a2 = City(tenant_id=tenant_id, code="city-a2", name="City A2")
                db.add(city_a2)
                db.flush()
                created["city_a2"] = city_a2.id

    yield created

    for tenant_id in (TENANT_A, TENANT_B):
        with db.begin():
            set_tenant(db, str(tenant_id))
            db.execute(text("DELETE FROM prices WHERE tenant_id = :t"), {"t": str(tenant_id)})
            db.execute(text("DELETE FROM item_aliases WHERE tenant_id = :t"), {"t": str(tenant_id)})
            db.execute(text("DELETE FROM items WHERE tenant_id = :t"), {"t": str(tenant_id)})
            db.execute(text("DELETE FROM cities WHERE tenant_id = :t"), {"t": str(tenant_id)})


def seed_prices(
    db: Session,
    tenant_id: uuid.UUID,
    item_id: uuid.UUID,
    city_id: uuid.UUID,
    count: int,
    *,
    start: datetime | None = None,
    step: timedelta = timedelta(minutes=10),
    sell_price_min: int = 100,
) -> None:
    """Insere `count` snapshots de preço espaçados por `step`, terminando em `start`
    (ou agora, se omitido) — usado pelos testes de /prices (raw e agregação).
    """
    start = start or datetime.now(UTC)
    with db.begin():
        set_tenant(db, str(tenant_id))
        rows = [
            {
                "item_id": item_id,
                "city_id": city_id,
                "sell_price_min": sell_price_min + i,
                "sell_price_max": sell_price_min + i + 10,
                "buy_price_min": sell_price_min - 20 + i,
                "buy_price_max": sell_price_min - 10 + i,
                "quality": 1,
                "qty": 5 + i,
                "collected_at": start - step * (count - i - 1),
            }
            for i in range(count)
        ]
        record_prices(db, tenant_id, rows)
