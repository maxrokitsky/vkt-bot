from typing import Any

from vkt_bot.core.models.event import EventRecord
from vkt_bot.db.repository import AsyncRepository


class EventRepository(AsyncRepository[EventRecord, int, Any, Any]):
    """Репозиторий журнала событий.

    Записываются события через ``core.events.emit`` — он собирает строку
    сам, чтобы вызывающему не приходилось помнить про ``trace_id`` и
    рендер ``summary``. Здесь остаётся чтение.
    """
