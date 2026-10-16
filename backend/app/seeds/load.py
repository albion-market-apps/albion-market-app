"""Popula o tenant "default", todas as cidades oficiais e um catálogo inicial
de itens (com aliases de busca). Idempotente: pode ser executado várias vezes
sem duplicar linhas nem violar as unique constraints.

TODO: catálogo de itens é parcial (~20 exemplos) — expandir via
Albion Online Data Project / ao-bin-dumps quando o coletor real estiver
pronto (ver worker/worker_app/collector.py).

Uso: `python -m app.seeds.load` (dentro do container da API).
"""

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.rls import set_tenant
from app.db.session import SessionLocal
from app.models.city import City
from app.models.item import Item, ItemAlias
from app.models.tenant import Tenant

_SEEDS_DIR = Path(__file__).parent
settings = get_settings()


def _load_json(name: str) -> list[dict]:
    return json.loads((_SEEDS_DIR / name).read_text(encoding="utf-8"))


def _seed_tenant(db: Session, tenant_id: UUID) -> None:
    """Garante que existe um tenant "default". Busca por `slug`, não por
    `id`: no MVP (1 tenant) só pode existir um "default", e `slug` tem
    unique constraint global — se buscássemos só por `id`, mudar
    TENANT_DEFAULT_ID no `.env` depois de já ter rodado o seed uma vez
    quebraria com `duplicate key value violates ... tenants_slug_key`.
    """
    existing = db.scalar(select(Tenant).where(Tenant.slug == "default"))
    if existing is None:
        db.add(Tenant(id=tenant_id, name="Default", slug="default"))
        db.flush()
    elif existing.id != tenant_id:
        print(
            f"AVISO: TENANT_DEFAULT_ID atual ({tenant_id}) não bate com o tenant "
            f"'default' já existente no banco ({existing.id}). Mantendo o existente — "
            "ajuste o .env para usar o id já gravado, ou migre os dados manualmente."
        )


def _seed_cities(db: Session, tenant_id: UUID) -> None:
    for city in _load_json("cities.json"):
        exists = db.scalar(
            select(City).where(City.tenant_id == tenant_id, City.code == city["code"])
        )
        if not exists:
            db.add(City(tenant_id=tenant_id, code=city["code"], name=city["name"]))
    db.flush()


def _get_item(db: Session, tenant_id: UUID, code: str, enchant: int) -> Item | None:
    return db.scalar(
        select(Item).where(Item.tenant_id == tenant_id, Item.code == code, Item.enchant == enchant)
    )


def _seed_items(db: Session, tenant_id: UUID) -> None:
    for item in _load_json("items.json"):
        if not _get_item(db, tenant_id, item["code"], item["enchant"]):
            db.add(
                Item(
                    tenant_id=tenant_id,
                    code=item["code"],
                    name=item["name"],
                    tier=item["tier"],
                    enchant=item["enchant"],
                )
            )
    db.flush()


def _seed_item_aliases(db: Session, tenant_id: UUID) -> None:
    for entry in _load_json("item_aliases.json"):
        item = _get_item(db, tenant_id, entry["code"], entry["enchant"])
        if item is None:
            continue  # item ainda não existe no catálogo deste tenant — ignora o alias
        exists = db.scalar(
            select(ItemAlias).where(
                ItemAlias.tenant_id == tenant_id,
                ItemAlias.item_id == item.id,
                ItemAlias.alias == entry["alias"],
            )
        )
        if not exists:
            db.add(ItemAlias(tenant_id=tenant_id, item_id=item.id, alias=entry["alias"]))
    db.flush()


def run() -> None:
    db = SessionLocal()
    tenant_id = UUID(settings.tenant_default_id)
    try:
        # `tenants` não tem RLS, mas cities/items/item_aliases têm — set_tenant
        # precisa estar na MESMA transação de todos os inserts (SET LOCAL só
        # vale até o commit).
        with db.begin():
            set_tenant(db, str(tenant_id))
            _seed_tenant(db, tenant_id)
            _seed_cities(db, tenant_id)
            _seed_items(db, tenant_id)
            _seed_item_aliases(db, tenant_id)

        print("Seed concluído: tenant default + cidades oficiais + catálogo de itens + aliases.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
