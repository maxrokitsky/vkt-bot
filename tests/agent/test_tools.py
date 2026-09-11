"""Реестр инструментов."""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext

from vkt_agent import AgentDeps, ToolRegistry


class TestRegistry:
    """``ToolRegistry``."""

    def test_registers_by_function_name(self) -> None:
        registry = ToolRegistry()

        @registry.tool
        async def user_roles(ctx: RunContext[AgentDeps]) -> str:
            """Роли."""
            return ""

        assert [spec.name for spec in registry.specs()] == ["user_roles"]
        assert "user_roles" in registry

    def test_keeps_metadata(self) -> None:
        registry = ToolRegistry()

        @registry.tool(mutates=True, admin_only=True)
        async def assign_role(ctx: RunContext[AgentDeps]) -> str:
            """Назначить роль."""
            return ""

        spec = registry.get("assign_role")
        assert spec is not None
        assert spec.mutates is True
        assert spec.admin_only is True

    def test_specs_are_sorted(self) -> None:
        """Порядок фиксирован: иначе префикс промпта плывёт и кэш мимо."""
        registry = ToolRegistry()

        @registry.tool
        async def zeta(ctx: RunContext[AgentDeps]) -> str:
            """z."""
            return ""

        @registry.tool
        async def alpha(ctx: RunContext[AgentDeps]) -> str:
            """a."""
            return ""

        assert [spec.name for spec in registry.specs()] == ["alpha", "zeta"]

    def test_duplicate_name_is_an_error(self) -> None:
        registry = ToolRegistry()

        @registry.tool(name="same")
        async def one(ctx: RunContext[AgentDeps]) -> str:
            """1."""
            return ""

        with pytest.raises(ValueError, match="уже зарегистрирован"):

            @registry.tool(name="same")
            async def two(ctx: RunContext[AgentDeps]) -> str:
                """2."""
                return ""
