"""Политика: что инструменту можно без спроса.

Три исхода. ``ALLOW`` — выполняется сразу, так живут все read-only
инструменты. ``ASK`` — нужно подтверждение человека кнопкой; так будут
жить мутирующие. ``DENY`` — актору не положено по правам, и модель
получает внятный текст, который может пересказать пользователю.

Политика вынесена из инструментов, чтобы правило было одно на всех: в
инструменте его легко забыть, а забытая проверка на мутирующем
инструменте — это действие от чужого имени.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .deps import AgentDeps
    from .tools import ToolSpec


class Decision(enum.StrEnum):
    """Исход проверки."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Policy:
    """Правило по умолчанию.

    Порядок важен: права проверяются раньше подтверждения. Иначе у
    постороннего сначала спросили бы разрешение на действие, которое ему
    всё равно не положено.
    """

    def decide(self, spec: ToolSpec, deps: AgentDeps) -> Decision:
        """Что делать с вызовом инструмента."""
        if spec.admin_only and not deps.actor.is_admin:
            return Decision.DENY
        if spec.mutates:
            return Decision.ASK
        return Decision.ALLOW

    def denial_reason(self, spec: ToolSpec, deps: AgentDeps) -> str:  # noqa: ARG002
        """Текст отказа для модели.

        Пишется человеческим языком: модель перескажет его пользователю,
        и «PermissionError» в чате выглядело бы дико.
        """
        return (
            f"Инструмент «{spec.name}» доступен только администраторам бота. "
            "Скажи об этом пользователю и попробуй ответить без него."
        )
