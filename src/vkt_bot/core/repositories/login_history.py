from typing import Any

from pydantic import BaseModel

from vkt_bot.core.models.login_history import LoginHistory
from vkt_bot.db.repository import AsyncRepository


class CreateLoginHistorySchema(BaseModel):
    """CreateLoginHistorySchema."""

    user_id: str
    ip_address: str | None = None
    user_agent: str | None = None


class LoginHistoryRepository(
    AsyncRepository[LoginHistory, int, CreateLoginHistorySchema, Any]
):
    """Login History Repository."""

    async def log_login(
        self, user_id: str, ip_address: str | None, user_agent: str | None
    ) -> LoginHistory:
        """Записать вход пользователя."""
        return await self.create(
            CreateLoginHistorySchema(
                user_id=user_id, ip_address=ip_address, user_agent=user_agent
            )
        )
