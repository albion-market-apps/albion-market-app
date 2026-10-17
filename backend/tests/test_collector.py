from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.rls import set_tenant
from app.models.item import Item
from app.models.price import Price
from app.services import collector
from tests.conftest import TENANT_A


def test_collect_once_persists_known_items_and_skips_zero_and_unknown(
    monkeypatch, db: Session, world: dict
) -> None:
    """`collect_once` precisa: (1) casar `code@enchant` com a convenção da AODP
    pra itens encantados, (2) ignorar item/cidade que a AODP devolveu mas não
    existe no catálogo do tenant, e (3) ignorar linhas sem nenhuma oferta
    (sell_price_min e buy_price_max ambos 0) — gravar isso seria tratar "sem
    dado" como um preço real de 0, o que quebraria a comparação entre cidades.
    """
    with db.begin():
        set_tenant(db, str(TENANT_A))
        enchanted = Item(
            tenant_id=TENANT_A,
            code="ITEM_A",
            name="Item A encantado",
            tier=4,
            enchant=1,
        )
        db.add(enchanted)
        db.flush()
        enchanted_id = enchanted.id

    def fake_fetch(unique_names: list[str], city_codes: list[str]) -> list[dict]:
        assert set(unique_names) == {"ITEM_A", "ITEM_A@1"}
        assert "city-a" in city_codes
        return [
            {
                "item_id": "ITEM_A",
                "city": "city-a",
                "sell_price_min": 100,
                "sell_price_max": 110,
                "buy_price_min": 80,
                "buy_price_max": 90,
                "quality": 1,
            },
            {
                "item_id": "ITEM_A@1",
                "city": "city-a",
                "sell_price_min": 500,
                "sell_price_max": 520,
                "buy_price_min": 400,
                "buy_price_max": 410,
                "quality": 1,
            },
            # sem nenhuma oferta real — não deve gerar linha.
            {
                "item_id": "ITEM_A",
                "city": "city-a2",
                "sell_price_min": 0,
                "sell_price_max": 0,
                "buy_price_min": 0,
                "buy_price_max": 0,
                "quality": 1,
            },
            # item que a AODP conhece mas não existe no catálogo deste tenant.
            {
                "item_id": "ITEM_DESCONHECIDO",
                "city": "city-a",
                "sell_price_min": 10,
                "sell_price_max": 20,
                "buy_price_min": 5,
                "buy_price_max": 8,
                "quality": 1,
            },
        ]

    monkeypatch.setattr(collector, "_fetch_aodp_prices", fake_fetch)

    created = collector.collect_once(TENANT_A)
    assert created == 2

    with db.begin():
        set_tenant(db, str(TENANT_A))
        rows = list(db.scalars(select(Price).where(Price.city_id == world["city_a"])))

    by_item = {row.item_id: row for row in rows}
    assert by_item[world["item_a"]].sell_price_min == 100
    assert by_item[enchanted_id].sell_price_min == 500
