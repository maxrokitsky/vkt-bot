"""Запуск сессии агента: лимиты, таймаут, прогресс.

Обёртка над ``Agent.run``. Она отвечает за то, чего у библиотеки нет:
общий таймаут на сессию, потолок вызовов инструментов, сбор расхода
токенов и отчёт о шагах в чат.

Ни одно из исключений наружу не выходит: молчащий бот хуже бота,
сказавшего «не смог, вот причина».
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Any

import structlog
from pydantic_ai import (
    Agent,
    RunContext,
    UsageLimitExceeded,
    UsageLimits,
    capture_run_messages,
)
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelResponse,
    TextPart,
    ToolCallPart,
)

from .deps import AgentDeps
from .events import OnStep, Step, StepKind
from .policy import Policy

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Sequence

    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model

    from .tools import ToolRegistry

logger = structlog.get_logger("vkt_agent.runner")

#: Что сказать, если модель не оставила ни одного текстового ответа.
EMPTY_ANSWER = "Не получилось собрать ответ."


@dataclasses.dataclass(slots=True)
class RunResult:
    """Итог сессии."""

    output: str
    #: Инструменты в порядке вызова — для журнала и для панели.
    tools: list[str] = dataclasses.field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    #: Новые сообщения диалога в сериализуемом виде: из них собирается
    #: продолжение разговора на следующем вопросе.
    messages: list[ModelMessage] = dataclasses.field(default_factory=list)
    #: Упёрлись в лимит шагов или в таймаут — ответ неполный.
    stopped_early: bool = False
    #: Текст ошибки, если сессия сорвалась.
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Сессия дошла до ответа."""
        return self.error is None


class AgentRunner:
    """Агент с лимитами.

    Экземпляр переживает много сессий: ``Agent`` собирается один раз,
    системный промпт и список инструментов не меняются — так у шлюза
    попадает кэш префикса.
    """

    def __init__(
        self,
        model: Model | str,
        *,
        registry: ToolRegistry,
        instructions: str,
        policy: Policy | None = None,
        max_steps: int = 8,
        timeout: float = 120.0,
    ) -> None:
        self.max_steps = max_steps
        self.timeout = timeout
        self.registry = registry
        self.agent: Agent[AgentDeps, str] = Agent(
            model,
            deps_type=AgentDeps,
            instructions=instructions,
            toolsets=[registry.toolset(policy or Policy())],
        )

    async def run(
        self,
        deps: AgentDeps,
        prompt: str,
        *,
        message_history: Sequence[ModelMessage] | None = None,
        on_step: OnStep | None = None,
    ) -> RunResult:
        """Провести сессию и вернуть отчёт.

        ``message_history`` продолжает разговор: в обсуждении второй
        вопрос должен помнить первый.
        """

        async def handler(
            ctx: RunContext[AgentDeps],  # noqa: ARG001
            stream: AsyncIterable[Any],
        ) -> None:
            async for event in stream:
                step = _as_step(event)
                if step is not None and on_step is not None:
                    await on_step(step)

        with capture_run_messages() as captured:
            try:
                async with asyncio.timeout(self.timeout):
                    result = await self.agent.run(
                        prompt,
                        deps=deps,
                        message_history=list(message_history or []),
                        # Потолок именно на вызовы инструментов: запросов
                        # к модели всегда на один больше — тот, в котором
                        # она формулирует ответ.
                        usage_limits=UsageLimits(tool_calls_limit=self.max_steps),
                        # Обработчик событий переводит запрос в стриминг,
                        # поэтому ставится только когда прогресс кому-то
                        # нужен: без него хватает обычного запроса.
                        event_stream_handler=handler if on_step else None,
                    )
            except UsageLimitExceeded:
                logger.warning(
                    "agent.step_limit_reached",
                    max_steps=self.max_steps,
                    chat_id=deps.chat_id,
                )
                spent = _spent(captured)
                return RunResult(
                    output=_last_text(captured)
                    or (
                        "Я сделал столько шагов, сколько мне разрешено, "
                        "и до ответа не дошёл. Попробуй спросить конкретнее."
                    ),
                    tools=_called_tools(captured),
                    input_tokens=spent[0],
                    output_tokens=spent[1],
                    messages=list(captured),
                    stopped_early=True,
                )
            except TimeoutError:
                logger.warning(
                    "agent.timeout", timeout=self.timeout, chat_id=deps.chat_id
                )
                spent = _spent(captured)
                return RunResult(
                    output=_last_text(captured)
                    or "Я думал слишком долго и остановился.",
                    tools=_called_tools(captured),
                    input_tokens=spent[0],
                    output_tokens=spent[1],
                    messages=list(captured),
                    stopped_early=True,
                )
            except Exception as exc:
                logger.exception("agent.failed", chat_id=deps.chat_id)
                spent = _spent(captured)
                return RunResult(
                    output="Не получилось ответить: внутренняя ошибка.",
                    tools=_called_tools(captured),
                    input_tokens=spent[0],
                    output_tokens=spent[1],
                    messages=list(captured),
                    error=f"{type(exc).__name__}: {exc}",
                )

        usage = result.usage
        new_messages = list(result.new_messages())
        return RunResult(
            output=result.output or EMPTY_ANSWER,
            tools=_called_tools(new_messages),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            messages=new_messages,
        )


def _as_step(event: Any) -> Step | None:  # noqa: ANN401
    """Событие библиотеки → шаг для чата."""
    if isinstance(event, FunctionToolCallEvent):
        return Step(kind=StepKind.TOOL_CALL, tool=event.part.tool_name)
    if isinstance(event, FunctionToolResultEvent):
        return Step(
            kind=StepKind.TOOL_RESULT, tool=getattr(event.part, "tool_name", None)
        )
    return None


def _spent(messages: Sequence[ModelMessage]) -> tuple[int, int]:
    """Сколько токенов уже израсходовано, по ответам модели.

    Нужно там, где сессия оборвалась и ``RunResult`` библиотеки не
    достался: упёрлись в лимит шагов, вышел таймаут, упал шлюз. Запросы к
    этому моменту уже сделаны и оплачены — не посчитать их значит
    систематически занижать расход и раздавать бюджет бесплатно.
    """
    incoming = outgoing = 0
    for message in messages:
        usage = getattr(message, "usage", None)
        if usage is None:
            continue
        incoming += getattr(usage, "input_tokens", 0) or 0
        outgoing += getattr(usage, "output_tokens", 0) or 0
    return incoming, outgoing


def _called_tools(messages: Sequence[ModelMessage]) -> list[str]:
    """Какие инструменты модель вызвала, в порядке вызова.

    Считается по сообщениям, а не по потоку событий: поток есть только в
    стриминге, а список вызванных инструментов нужен всегда — он идёт и в
    журнал, и в панель.
    """
    called: list[str] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        called.extend(
            part.tool_name for part in message.parts if isinstance(part, ToolCallPart)
        )
    return called


def _last_text(messages: Sequence[ModelMessage]) -> str | None:
    """Последний текст, который модель успела произнести.

    Нужен, когда сессия оборвалась по лимиту: то, что уже собрано,
    полезнее пустоты.
    """
    for message in reversed(list(messages)):
        if not isinstance(message, ModelResponse):
            continue
        for part in reversed(message.parts):
            if isinstance(part, TextPart) and part.content.strip():
                return part.content
    return None
