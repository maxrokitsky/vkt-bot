

from pydantic import BaseModel


class DetailChatUserAPISchema(BaseModel):
    """Чат-юзер."""

    id: str
    roles: list[str]
