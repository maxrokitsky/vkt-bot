import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class VktSettings(BaseSettings):
    """Конфигурация."""

    logging: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]  # = 'INFO'
    #: Рендерер логов. ``auto`` — ``console`` при TTY, иначе ``json``.
    log_format: Literal["auto", "console", "json"] = "auto"
    #: Точечные уровни логгеров: ``"sqlalchemy.engine=WARNING,aiohttp=DEBUG"``.
    #: Строка, а не словарь: pydantic-settings разбирает сложные типы через
    #: ``json.loads`` и падает на человеческой записи. Разбор — в
    #: ``logging_setup.parse_log_levels``.
    log_levels: str = ""
    #: Окружение: попадает в каждую строку лога и в метку Loki.
    env: Literal["local", "stage", "prod"] = "local"
    #: Имя сервиса в логах: бот и веб-сервер запускаются отдельно.
    service_name: str = "vkt-bot"
    bot_token: str
    db_url: PostgresDsn
    owner_id: str | None = None
    log_file: Path | None = None
    secret_key: str  # Required for JWT authentication
    public_url: str | None = None
    sentry_dsn: str | None = None
    access_token_expire_minutes: int = 60 * 24 * 8
    #: Сколько дней хранить рутинные события журнала. Предупреждения и
    #: ошибки не удаляются никогда; ``0`` выключает чистку.
    events_retention_days: int = 90
    #: Сколько дней хранить историю сообщений. ``0`` выключает чистку.
    messages_retention_days: int = 30
    #: Потолок строк истории на один чат. Нужен рядом со сроком хранения:
    #: болтливый чат набирает миллионы строк раньше, чем срок истечёт.
    #: ``0`` снимает ограничение.
    messages_max_per_chat: int = 10_000

    #: Redis под очередь задач. Пусто — задачи исполняются в процессе
    #: бота, как раньше: локальная разработка и тесты не должны требовать
    #: поднятого Redis. В боевом окружении это заметная деградация,
    #: поэтому она громкая — предупреждение в первой же строке лога.
    redis_url: RedisDsn | None = None
    #: Имя списка задач в Redis. Отдельное, потому что stage и prod
    #: обычно делят один инстанс, а перемешать их очереди — это ответы
    #: агента не в тот чат.
    task_queue: str = "vkt-bot-tasks"

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

    @field_validator("redis_url", mode="before")
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:  # noqa: ANN401
        """Пустая строка — «Redis нет».

        ``os.environ`` перебивает ``.env`` только если переменная задана,
        поэтому пустым ``REDIS_URL`` тесты гасят боевое значение с машины
        разработчика. Пустую строку ``RedisDsn`` не принимает.
        """
        return value or None

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
