"""Настройки агента.

Свой ``BaseSettings`` с префиксом ``AI_``: плагин не должен требовать
правок в ядре. У ``VktSettings`` стоит ``extra="ignore"``, поэтому лишние
``AI_*`` в ``.env`` его не ломают.

Читается лениво, как ``config.get_settings()``: импорт модуля не требует
``.env``, и без ключа шлюза бот запускается — просто без агента.
"""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict

from vkt_agent import DEFAULT_BASE_URL


class AiSettings(BaseSettings):
    """Конфигурация ИИ-агента."""

    #: Выключатель в ``.env``. Гасить на ходу — ``ai_enabled`` в
    #: ``bot_settings``, чтобы не перезапускать бота.
    enabled: bool = False
    #: OpenAI-совместимый шлюз. По умолчанию — OpenRouter.
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    #: Как модель называется у шлюза. У OpenRouter — с вендором в
    #: префиксе (``anthropic/claude-sonnet-5``, ``openai/gpt-4.1``).
    model: str = "anthropic/claude-sonnet-5"

    #: Вызовов инструментов на сессию. Упёрлись — агент отвечает тем,
    #: что успел собрать, и говорит, что остановился.
    max_steps: int = 8
    #: Таймаут на всю сессию, а не на запрос.
    timeout_seconds: float = 120.0
    #: Одновременных сессий: лимиты у шлюза общие на всех.
    max_concurrent: int = 3
    #: Токенов на пользователя в сутки; ``0`` — без лимита.
    daily_token_budget: int = 200_000

    #: Сколько последних сообщений чата класть в промпт.
    context_messages: int = 20
    #: Потолок объёма истории в промпте: один болтливый чат иначе съест
    #: весь бюджет токенов.
    context_chars: int = 8_000

    #: Сколько дней хранить диалоги с агентом. Тексты промптов и ответов
    #: — чувствительные данные, поэтому срок короче, чем у журнала.
    retention_days: int = 30

    model_config = SettingsConfigDict(
        env_prefix="AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@functools.lru_cache(maxsize=1)
def get_ai_settings() -> AiSettings:
    """Настройки агента; валидируются при первом обращении."""
    return AiSettings()
