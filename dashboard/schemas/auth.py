from pydantic import BaseModel


class Token(BaseModel):
    """Токен."""

    access_token: str
    token_type: str = 'bearer'


class TokenPayload(BaseModel):
    sub: str | None = None
