from app.schemas.base import TimestampedModel


class CityOut(TimestampedModel):
    code: str
    name: str
