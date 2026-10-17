from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.rls import get_current_tenant_id, get_tenant_db
from app.models.city import City
from app.schemas.cities import CityOut

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("", response_model=list[CityOut])
def list_cities(
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[CityOut]:
    cities = db.scalars(select(City).where(City.tenant_id == tenant_id).order_by(City.name)).all()
    return [CityOut.model_validate(city) for city in cities]
