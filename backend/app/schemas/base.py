from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base para schemas de leitura que vêm direto de um model SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedModel(ORMModel):
    id: UUID
    created_at: datetime
