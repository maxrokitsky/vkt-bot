"""Реестр инструментов: функция плюс метаданные.

JSON Schema параметров pydantic-ai собирает из сигнатуры и докстринга —
описывать её руками не нужно. От нас требуется то, чего в сигнатуре нет:
меняет ли инструмент состояние и кому он доступен. Это и есть
``ToolSpec``.

Реестр собирает из зарегистрированных функций ``FunctionToolset``,
подставляя перед каждым вызовом проверку политики.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog
from pydantic_ai import ApprovalRequired, RunContext
from pydantic_ai.toolsets import FunctionToolset

from .deps import AgentDeps
from .policy import Decision, Policy

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = structlog.get_logger("vkt_agent.tools")


@dataclasses.dataclass(frozen=True, slots=True)
class ToolSpec:
    """Метаданные инструмента."""

    name: str
    #: Меняет состояние — значит, нужно подтверждение человека.
    mutates: bool = False
    #: Доступен только администратору. Проверяется по актору, не по
    #: тому, что о себе говорит модель.
    admin_only: bool = False


class ToolRegistry:
    """Набор инструментов агента.

    Хранит функции вместе со спецификациями и умеет отдать их
    ``FunctionToolset``, обёрнутыми проверкой политики.
    """

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}

    def tool(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        mutates: bool = False,
        admin_only: bool = False,
    ) -> Any:  # noqa: ANN401
        """Зарегистрировать инструмент.

        Работает и как ``@registry.tool``, и как
        ``@registry.tool(admin_only=True)``.
        """

        def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
            spec = ToolSpec(
                name=name or target.__name__,
                mutates=mutates,
                admin_only=admin_only,
            )
            if spec.name in self._tools:
                msg = f"Инструмент {spec.name!r} уже зарегистрирован"
                raise ValueError(msg)
            self._tools[spec.name] = (spec, target)
            return target

        if func is not None:
            return decorator(func)
        return decorator

    def specs(self) -> list[ToolSpec]:
        """Спецификации, отсортированные по имени.

        Порядок фиксированный: список инструментов уходит в промпт, а
        стабильный префикс — условие того, что кэш на шлюзе попадает.
        """
        return sorted((spec for spec, _ in self._tools.values()), key=lambda s: s.name)

    def get(self, name: str) -> ToolSpec | None:
        """Спецификация по имени."""
        found = self._tools.get(name)
        return found[0] if found else None

    def toolset(self, policy: Policy | None = None) -> FunctionToolset[AgentDeps]:
        """Собрать toolset с проверкой политики перед каждым вызовом."""
        policy = policy or Policy()
        toolset: FunctionToolset[AgentDeps] = FunctionToolset()
        for spec, func in sorted(self._tools.values(), key=lambda item: item[0].name):
            toolset.add_function(
                _guard(spec, func, policy),
                name=spec.name,
                takes_ctx=True,
                docstring_format="google",
            )
        return toolset

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools


def _guard(
    spec: ToolSpec, func: Callable[..., Any], policy: Policy
) -> Callable[..., Any]:
    """Обернуть инструмент проверкой политики.

    Обёртка сохраняет сигнатуру и докстринг оригинала: из них pydantic-ai
    собирает JSON Schema, и подмена на ``*args, **kwargs`` оставила бы
    модель без описания параметров.
    """
    import functools

    @functools.wraps(func)
    async def guarded(ctx: RunContext[AgentDeps], *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        decision = policy.decide(spec, ctx.deps)
        logger.debug(
            "agent.tool_policy",
            tool=spec.name,
            decision=decision.value,
            actor_id=ctx.deps.actor.user_id,
        )
        if decision is Decision.DENY:
            # Отказ — это результат инструмента, а не исключение:
            # ``ModelRetry`` съедал бы попытки и на упрямой модели ронял
            # сессию, а так модель просто читает причину и отвечает без
            # этого инструмента.
            return policy.denial_reason(spec, ctx.deps)
        if decision is Decision.ASK:
            # Подтверждение кнопкой — вторая фаза. Механика pydantic-ai
            # уже здесь: вызов уходит в отложенные и ждёт решения.
            raise ApprovalRequired
        return await func(ctx, *args, **kwargs)

    return guarded


def tool_lines(specs: Iterable[ToolSpec]) -> list[str]:
    """Имена инструментов для промпта — в фиксированном порядке."""
    return [spec.name for spec in specs]
