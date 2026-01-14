import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model


class BotSettings(Model):
    """Настройки бота."""

    __tablename__ = "bot_settings"

    key: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    value: orm.Mapped[str] = orm.mapped_column(sa.Text)
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )
    description: orm.Mapped[str | None] = orm.mapped_column(sa.Text, nullable=True)
