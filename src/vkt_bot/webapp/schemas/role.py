import datetime as dt
import uuid

from pydantic import BaseModel


class CreateRoleAPISchema(BaseModel):
    """Роль."""

    name: str


class DetailRoleAPISchema(BaseModel):
    """Роль."""

    id: uuid.UUID
    name: str
    created_at: dt.datetime
