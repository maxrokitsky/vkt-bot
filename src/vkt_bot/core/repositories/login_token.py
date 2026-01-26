import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkt_bot.core.models.login_token import LoginToken
from vkt_bot.db.repository import AsyncRepository


class CreateLoginTokenSchema(BaseModel):
    """CreateLoginTokenSchema."""

    token: str
    user_id: str
    expires_at: datetime


class LoginTokenRepository(
    AsyncRepository[LoginToken, int, CreateLoginTokenSchema, Any]
):
    """Login Token Repository."""

    async def create_token(self, user_id: str, expires_minutes: int = 5) -> LoginToken:
        """Создать временный токен для входа."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        return await self.create(
            CreateLoginTokenSchema(token=token, user_id=user_id, expires_at=expires_at)
        )

    async def get_by_token(self, token: str) -> LoginToken | None:
        """Получить токен по значению."""
        stmt = sa.select(LoginToken).where(LoginToken.token == token)
        return await self.session.scalar(stmt)

    async def mark_used(self, login_token: LoginToken) -> None:
        """Отметить токен как использованный."""
        login_token.used = True
        self.session.add(login_token)

    async def cleanup_expired(self) -> int:
        """Удалить просроченные токены. Возвращает количество удалённых."""
        stmt = sa.delete(LoginToken).where(
            sa.or_(
                LoginToken.expires_at < datetime.now(timezone.utc),
                LoginToken.used == True,  # noqa: E712
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount
