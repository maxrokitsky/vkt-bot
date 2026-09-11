"""Схемы API агента.

Поля обязательные и без значений по умолчанию: иначе в сгенерированном
клиенте они становятся опциональными, и по фронтенду расползаются `?.`.
"""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel

from .models import SessionStatus


class AgentSessionResponse(BaseModel):
    """Сессия в списке."""

    id: uuid.UUID
    chat_id: str
    chat_title: str | None
    user_id: str
    user_name: str
    thread_id: str | None
    status: SessionStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    tokens_in: int
    tokens_out: int
    #: Первый вопрос диалога — без подложенной истории чата.
    question: str | None


class PaginatedAgentSessionsResponse(BaseModel):
    """Постраничный список сессий."""

    items: list[AgentSessionResponse]
    total: int
    page: int
    size: int
    pages: int


class AgentMessageResponse(BaseModel):
    """Сообщение диалога.

    ``raw`` наружу не отдаётся никогда: там лежит полный запрос к модели
    вместе с автоконтекстом.
    """

    id: int
    role: str
    content: str | None
    tool_name: str | None
    created_at: datetime.datetime


class AgentSessionDetailResponse(BaseModel):
    """Сессия целиком, с ходом диалога."""

    session: AgentSessionResponse
    messages: list[AgentMessageResponse]


class AgentUsagePoint(BaseModel):
    """Расход за один день."""

    date: datetime.date
    sessions: int
    tokens: int


class AgentUsageActor(BaseModel):
    """Расход по участнику или чату."""

    id: str
    name: str
    sessions: int
    tokens: int


class AgentUsageTotals(BaseModel):
    """Итоги за период."""

    sessions: int
    tokens_in: int
    tokens_out: int
    #: Сколько человек за период вообще обращались к агенту.
    users: int
    failed: int


class AgentUsageResponse(BaseModel):
    """Расход токенов.

    Админ видит всех, обычный участник — только себя: вопрос к агенту
    говорит о человеке не меньше, чем сам ответ.
    """

    days: int
    totals: AgentUsageTotals
    by_day: list[AgentUsagePoint]
    top_users: list[AgentUsageActor]
    top_chats: list[AgentUsageActor]
    #: Суточный бюджет на человека; 0 — без лимита.
    daily_token_budget: int
    #: Сколько спрашивающий израсходовал сегодня — из того же счётчика,
    #: по которому команда `/ai` отказывает.
    spent_today: int


class AgentStatusResponse(BaseModel):
    """Состояние агента: включён ли и с какими лимитами."""

    #: Хватает ли настроек в `.env`.
    configured: bool
    #: Итог: настроен и не выключен в `bot_settings`.
    enabled: bool
    model: str
    max_steps: int
    context_messages: int
    daily_token_budget: int
    retention_days: int
