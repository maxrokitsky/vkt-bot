import datetime

from pydantic import BaseModel


class OverviewCounts(BaseModel):
    """Счётчики для плиток обзора."""

    chats: int
    chat_users: int
    roles: int
    webhooks: int
    webhooks_active: int


class ActivityPoint(BaseModel):
    """Число действий за один день."""

    date: datetime.date
    count: int


class OverviewResponse(BaseModel):
    counts: OverviewCounts
    #: Активность по дням. Данные берутся из аудита, поэтому не-админ
    #: получает пустой список — журнал ему недоступен.
    activity: list[ActivityPoint] = []
    activity_days: int
