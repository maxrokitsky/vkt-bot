"""Модель провайдера.

Слой абстракции у нас один — pydantic-ai; шлюз выглядит как OpenAI, и
этого достаточно: OpenAI-совместимый шейп эмулируют все (OpenRouter,
litellm, vLLM, Ollama, корпоративные прокси). Появится провайдер с другим
протоколом — здесь добавится ещё одна фабрика, остальной код не изменится.
"""

from __future__ import annotations

from urllib.parse import urlparse

import structlog
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = structlog.get_logger("vkt_agent.models")

#: Шлюз по умолчанию. Имя модели у OpenRouter — с вендором в префиксе
#: (``anthropic/claude-sonnet-5``, ``openai/gpt-4.1``).
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def openai_compatible_model(
    model_name: str,
    *,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
) -> OpenAIChatModel:
    """Модель у OpenAI-совместимого шлюза.

    Имя класса менялось между версиями pydantic-ai
    (``OpenAIModel`` → ``OpenAIChatModel``), поэтому версия
    зафиксирована в ``pyproject.toml``, а импорт — здесь, в одном месте.
    """
    if api_key and urlparse(base_url).scheme != "https":
        # Предупреждение, а не отказ: внутренний шлюз в закрытом контуре
        # по http — законная конфигурация, и ронять из-за неё бота нельзя.
        # Но ключ при этом уходит по незашифрованному соединению, и знать
        # об этом администратор должен.
        logger.warning(
            "agent.insecure_gateway",
            scheme=urlparse(base_url).scheme,
            host=urlparse(base_url).hostname,
        )
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )
