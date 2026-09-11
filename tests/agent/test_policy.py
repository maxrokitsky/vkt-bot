"""Политика подтверждений."""

from __future__ import annotations

import pytest

from vkt_agent import AgentActor, AgentDeps, Decision, Policy, ToolSpec

READ_ONLY = ToolSpec(name="user_roles")
MUTATING = ToolSpec(name="assign_role", mutates=True)
ADMIN_ONLY = ToolSpec(name="secrets", admin_only=True)
ADMIN_MUTATING = ToolSpec(name="drop_all", mutates=True, admin_only=True)


def deps(*, is_admin: bool) -> AgentDeps:
    return AgentDeps(
        session=None,  # type: ignore[arg-type]
        actor=AgentActor(user_id="u1", display_name="Иван", is_admin=is_admin),
        chat_id="c1",
    )


class TestDecide:
    """``Policy.decide``."""

    @pytest.mark.parametrize(
        ("spec", "is_admin", "expected"),
        [
            (READ_ONLY, False, Decision.ALLOW),
            (READ_ONLY, True, Decision.ALLOW),
            (MUTATING, False, Decision.ASK),
            (MUTATING, True, Decision.ASK),
            (ADMIN_ONLY, False, Decision.DENY),
            (ADMIN_ONLY, True, Decision.ALLOW),
            (ADMIN_MUTATING, False, Decision.DENY),
            (ADMIN_MUTATING, True, Decision.ASK),
        ],
    )
    def test_table(self, spec: ToolSpec, is_admin: bool, expected: Decision) -> None:
        assert Policy().decide(spec, deps(is_admin=is_admin)) is expected

    def test_admin_never_skips_confirmation(self) -> None:
        """Мутирующий инструмент не подтверждается сам — даже админу."""
        assert Policy().decide(MUTATING, deps(is_admin=True)) is Decision.ASK

    def test_denial_reason_is_human(self) -> None:
        reason = Policy().denial_reason(ADMIN_ONLY, deps(is_admin=False))
        assert "secrets" in reason
        assert "администратор" in reason
