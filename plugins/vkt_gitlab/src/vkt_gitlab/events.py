"""Типы событий плагина.

Регистрируются из ``install()``: колонка ``type`` хранит строку, поэтому
миграции для своих типов плагину не нужны.
"""

from vkt_bot.core.events import EventSpec, register
from vkt_bot.core.models.event import EventSeverity, EventSource

PIPELINE_SUCCEEDED = "gitlab.pipeline_succeeded"
PIPELINE_FAILED = "gitlab.pipeline_failed"

SPECS = (
    EventSpec(
        type=PIPELINE_SUCCEEDED,
        title="Пайплайн прошёл",
        template="Пайплайн {project} на ветке {branch} прошёл",
        source=EventSource.PLUGIN,
        chat_scoped=True,
    ),
    EventSpec(
        type=PIPELINE_FAILED,
        title="Пайплайн упал",
        template="Пайплайн {project} на ветке {branch} упал",
        source=EventSource.PLUGIN,
        severity=EventSeverity.WARNING,
        chat_scoped=True,
    ),
)


def install_events() -> None:
    """Зарегистрировать типы событий плагина."""
    register(*SPECS)
