import datetime
import secrets

import bcrypt
import sqlalchemy as sa

from vkt_bot.core.models import Webhook
from vkt_bot.db.repository import AsyncRepository
from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema, WebhookUpdateSchema


class WebhookRepository(
    AsyncRepository[Webhook, str, WebhookCreateSchema, WebhookUpdateSchema]
):
    """Репозиторий для управления вебхуками."""

    async def get_by_id_and_api_key(
        self, webhook_id: str, api_key: str
    ) -> Webhook | None:
        """Найти вебхук по ID и проверить API ключ."""
        webhook = await self.get_or_none(webhook_id)
        if not webhook:
            return None

        # Проверка хэша API ключа
        if not bcrypt.checkpw(api_key.encode(), webhook.api_key_hash.encode()):
            return None

        return webhook

    async def create_with_api_key(
        self, data: WebhookCreateSchema, creator_id: str
    ) -> tuple[Webhook, str]:
        """Создать вебхук с генерацией API ключа."""
        # Генерация API ключа
        api_key = secrets.token_urlsafe(32)
        api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

        # Создание вебхука - создаем словарь с данными и передаем в create
        webhook_data = {
            "name": data.name,
            "chat_id": data.chat_id,
            "webhook_metadata": data.webhook_metadata,
            "api_key_hash": api_key_hash,
            "created_by": creator_id,
        }

        # Используем create с dict вместо схемы
        webhook = await self.create(webhook_data, commit=True)
        return webhook, api_key  # Возвращаем вебхук и чистый ключ (только один раз!)

    async def list_by_creator(self, creator_id: str) -> list[Webhook]:
        """Получить список вебхуков созданных пользователем."""
        stmt = (
            sa.select(Webhook)
            .where(Webhook.created_by == creator_id)
            .order_by(Webhook.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_by_chat(self, chat_id: str) -> list[Webhook]:
        """Получить список вебхуков для чата."""
        stmt = (
            sa.select(Webhook)
            .where(Webhook.chat_id == chat_id)
            .order_by(Webhook.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def check_rate_limit(
        self, webhook_id: str, time_window_minutes: int = 1, max_requests: int = 10
    ) -> bool:
        """Проверить rate limiting для вебхука."""
        # TODO: Реализовать проверку rate limiting
        # Можно использовать Redis или таблицу в БД для хранения счетчиков
        return True

    async def log_webhook_call(
        self,
        webhook_id: str,
        success: bool,
        request_data: dict,
        response_data: dict,
        ip_address: str | None = None,
    ) -> None:
        """Записать вызов вебхука в лог."""
        # TODO: Реализовать логирование вызовов вебхуков
        # Можно создать отдельную таблицу для логов или использовать существующую LogEntry
        pass

    async def regenerate_api_key(self, webhook_id: str) -> tuple[Webhook, str]:
        """Перегенерировать API ключ для вебхука."""
        webhook = await self.get(webhook_id)

        # Генерация нового API ключа
        api_key = secrets.token_urlsafe(32)
        api_key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

        # Обновление вебхука
        webhook.api_key_hash = api_key_hash
        webhook.updated_at = datetime.datetime.now(datetime.timezone.utc)

        await self.session.commit()
        return webhook, api_key
