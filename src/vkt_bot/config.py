import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class VktSettings(BaseSettings):
    """Конфигурация."""

    logging: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]  # = 'INFO'
    rabbitmq_logging: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    bot_token: str
    db_url: PostgresDsn
    owner_id: str | None = None
    log_file: Path | None = None
    secret_key: str  # Required for JWT authentication
    public_url: str | None = None
    sentry_dsn: str | None = None
    access_token_expire_minutes: int = 60 * 24 * 8

    # Настройки для загрузки файлов
    max_file_size: int = 50 * 1024 * 1024  # 50 MB по умолчанию
    allowed_file_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> VktSettings:
    """Настройки приложения.

    Валидируются при первом обращении и кэшируются. Кидает
    ``pydantic.ValidationError``, если обязательные переменные не заданы;
    обрабатывать её и завершать процесс — дело точки входа (``main.py``).
    """
    return VktSettings()


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Ленивый доступ к ``vkt_bot.config.settings``.

    Позволяет импортировать модуль (и всё, что его импортирует) без
    полного окружения — настройки читаются только при первом обращении
    к ``settings``.
    """
    if name == "settings":
        return get_settings()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


if TYPE_CHECKING:
    # Для статических анализаторов: `from vkt_bot.config import settings`
    # разрешается через module-level __getattr__ выше.
    settings: VktSettings
