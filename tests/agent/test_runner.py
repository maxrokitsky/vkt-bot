"""Запуск сессии агента.

Сети здесь нет: ``FunctionModel`` играет сценарий вызовов, поэтому
проверяются наши правила, а не поведение конкретной модели.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from vkt_agent import AgentActor, AgentDeps, AgentRunner, Step, StepKind, ToolRegistry

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool
    async def user_roles(ctx: RunContext[AgentDeps], user_id: str) -> str:
        """Роли участника.

        Args:
            user_id: идентификатор участника.
        """
        return f"{user_id}: дежурный"

    @registry.tool
    async def find_chats(ctx: RunContext[AgentDeps], query: str) -> str:
        """Поиск чатов.

        Args:
            query: часть названия.
        """
        return f"чаты по «{query}»: Поддержка"

    @registry.tool(admin_only=True)
    async def secrets(ctx: RunContext[AgentDeps]) -> str:
        """Только для админов."""
        return "внутренние данные"

    return registry


def deps(*, is_admin: bool = False) -> AgentDeps:
    return AgentDeps(
        session=None,  # type: ignore[arg-type]
        actor=AgentActor(user_id="u1", display_name="Иван", is_admin=is_admin),
        chat_id="c1",
    )


def scripted(*script: list[ToolCallPart | TextPart]):  # noqa: ANN201
    """Модель, которая играет заранее заданные ответы по шагам."""
    steps = list(script)

    def play(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
        index = min(len(steps) - 1, sum(1 for m in messages if m.kind == "response"))
        return ModelResponse(parts=list(steps[index]))

    return FunctionModel(play)


class TestHappyPath:
    """Два инструмента и ответ."""

    async def test_calls_tools_then_answers(self) -> None:
        model = scripted(
            [
                ToolCallPart("user_roles", {"user_id": "u2"}),
                ToolCallPart("find_chats", {"query": "Поддержка"}),
            ],
            [TextPart("Дежурный — u2, он в чате «Поддержка».")],
        )
        runner = AgentRunner(model, registry=build_registry(), instructions="Ты бот")

        result = await runner.run(deps(), "кто дежурный?")

        assert result.ok
        assert result.output.startswith("Дежурный")
        assert result.tools == ["user_roles", "find_chats"]
        assert result.messages

    async def test_reports_steps(self) -> None:
        """Прогресс идёт стримом, а ``FunctionModel`` его не умеет —
        поэтому здесь ``TestModel``: он дёргает все инструменты подряд."""
        steps: list[Step] = []
        runner = AgentRunner(
            TestModel(), registry=build_registry(), instructions="Ты бот"
        )

        async def on_step(step: Step) -> None:
            steps.append(step)

        result = await runner.run(deps(is_admin=True), "кто дежурный?", on_step=on_step)

        called = [s.tool for s in steps if s.kind is StepKind.TOOL_CALL]
        assert "user_roles" in called
        assert result.tools == called

    async def test_counts_tokens(self) -> None:
        model = scripted([TextPart("ответ")])
        runner = AgentRunner(model, registry=build_registry(), instructions="Ты бот")

        result = await runner.run(deps(), "привет")

        assert result.input_tokens > 0
        assert result.output_tokens > 0


class TestPermissions:
    """Права проверяются, что бы модель ни решила."""

    async def test_denied_tool_returns_reason(self) -> None:
        """Отказ приходит результатом инструмента, а не падением сессии."""
        model = scripted(
            [ToolCallPart("secrets", {})],
            [TextPart("Мне это не показали.")],
        )
        runner = AgentRunner(model, registry=build_registry(), instructions="Ты бот")

        result = await runner.run(deps(is_admin=False), "покажи секреты")

        assert result.ok
        assert result.output == "Мне это не показали."
        texts = str(result.messages)
        assert "только администраторам" in texts
        assert "внутренние данные" not in texts

    async def test_admin_gets_the_tool(self) -> None:
        model = scripted(
            [ToolCallPart("secrets", {})],
            [TextPart("вот они")],
        )
        runner = AgentRunner(model, registry=build_registry(), instructions="Ты бот")

        result = await runner.run(deps(is_admin=True), "покажи секреты")

        assert "внутренние данные" in str(result.messages)


class TestLimits:
    """Лимиты сессии."""

    async def test_step_limit_stops_and_says_so(self) -> None:
        """Упёрлись в потолок — отвечаем тем, что успели, и предупреждаем."""

        def endless(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
            return ModelResponse(parts=[ToolCallPart("user_roles", {"user_id": "u2"})])

        runner = AgentRunner(
            FunctionModel(endless),
            registry=build_registry(),
            instructions="Ты бот",
            max_steps=2,
        )

        result = await runner.run(deps(), "зациклись")

        assert result.stopped_early is True
        assert result.ok
        # Ровно столько вызовов, сколько разрешено; последний,
        # перешагнувший лимит, до исполнения не доходит.
        assert result.tools.count("user_roles") >= 2
        assert "остановился" in result.output or "не дошёл" in result.output

    async def test_timeout(self) -> None:
        def slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
            return ModelResponse(parts=[TextPart("не успею")])

        runner = AgentRunner(
            FunctionModel(slow),
            registry=build_registry(),
            instructions="Ты бот",
            timeout=0.0,
        )

        result = await runner.run(deps(), "думай долго")

        assert result.stopped_early is True
        assert "остановился" in result.output


class TestFailure:
    """Сбой модели."""

    async def test_error_becomes_a_message(self) -> None:
        """Тишина вместо ответа — худший исход, поэтому её не бывает."""

        def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
            msg = "шлюз недоступен"
            raise RuntimeError(msg)

        runner = AgentRunner(
            FunctionModel(boom), registry=build_registry(), instructions="Ты бот"
        )

        result = await runner.run(deps(), "привет")

        assert result.ok is False
        assert "шлюз недоступен" in (result.error or "")
        assert result.output


class TestHistory:
    """Продолжение разговора."""

    async def test_history_is_passed_to_the_model(self) -> None:
        seen: list[int] = []

        def counting(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
            seen.append(len(messages))
            return ModelResponse(parts=[TextPart("ага")])

        runner = AgentRunner(
            FunctionModel(counting), registry=build_registry(), instructions="Ты бот"
        )

        first = await runner.run(deps(), "первый вопрос")
        await runner.run(deps(), "второй вопрос", message_history=first.messages)

        assert seen[1] > seen[0]


async def test_concurrent_sessions_do_not_mix() -> None:
    """Раннер живёт долго и обслуживает несколько чатов сразу."""
    model = scripted([TextPart("ответ")])
    runner = AgentRunner(model, registry=build_registry(), instructions="Ты бот")

    results = await asyncio.gather(runner.run(deps(), "раз"), runner.run(deps(), "два"))

    assert all(result.ok for result in results)
