import datetime as dt
from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, EmailStr


class CreateUserAPISchema(BaseModel):
    """Юзер."""

    username: str
    password: Annotated[str, Len(8, 40)]
    email: EmailStr


class UpdateUserAPISchema(BaseModel):
    """Юзер."""

    password: Annotated[str, Len(8, 40)]
    email: EmailStr


class PartialUpdateUserAPISchema(BaseModel):
    """Юзер."""

    password: Annotated[str, Len(8, 40)] | None = None
    email: EmailStr | None = None


class DetailUserAPISchema(BaseModel):
    """Юзер."""

    username: str
    email: EmailStr
    created_at: dt.datetime
