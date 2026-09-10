"""Каркас ИИ-агента.

Слоёв два, и они не путаются: pydantic-ai отвечает за диалект вызова
инструментов у провайдера, а этот пакет — за то, чего у библиотеки нет:
права актора, подтверждения, лимиты сессии и прогресс в чате.

``vkt_bot`` пакет не импортирует: всё, что специфично для приложения,
приезжает через ``AgentDeps``.
"""

from .deps import AgentActor, AgentDeps
from .events import OnStep, Step, StepKind
from .models import DEFAULT_BASE_URL, openai_compatible_model
from .policy import Decision, Policy
from .runner import AgentRunner, RunResult
from .tools import ToolRegistry, ToolSpec

__all__ = (
    "DEFAULT_BASE_URL",
    "AgentActor",
    "AgentDeps",
    "AgentRunner",
    "Decision",
    "OnStep",
    "Policy",
    "RunResult",
    "Step",
    "StepKind",
    "ToolRegistry",
    "ToolSpec",
    "openai_compatible_model",
)
