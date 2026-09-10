"""Модель провайдера.

Слой абстракции у нас один — pydantic-ai; шлюз выглядит как OpenAI, и
этого достаточно: OpenAI-совместимый шейп эмулируют все (OpenRouter,
litellm, vLLM, Ollama, корпоративные прокси). Появится провайдер с другим
протоколом — здесь добавится ещё одна фабрика, остальной код не изменится.
"""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

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
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )
