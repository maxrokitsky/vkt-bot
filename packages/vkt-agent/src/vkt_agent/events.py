"""Шаги агента: протокол прогресса.

В мессенджере стрима нет, поэтому «печатает…» изображается правкой
одного сообщения. Раннер сообщает о шагах через ``on_step``, а как это
показать — дело приложения.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Awaitable, Callable


class StepKind(enum.StrEnum):
    """Что произошло."""

    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TEXT = "text"


@dataclasses.dataclass(frozen=True, slots=True)
class Step:
    """Один шаг сессии."""

    kind: StepKind
    #: Имя инструмента — у текстовых шагов пусто.
    tool: str | None = None
    #: Короткое пояснение для человека.
    detail: str | None = None


#: Куда раннер сообщает о шагах.
type OnStep = Callable[[Step], Awaitable[None]]
