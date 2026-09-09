"""Движок и фабрика сессий SQLAlchemy.

Модуль импортируется на старте почти всем приложением, поэтому подключение
к БД создаётся лениво: до первого обращения к ``async_session`` ни движок,
ни настройки не нужны. Тесты подменяют DSN через
``async_session.configure(...)``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_session_factory(
    url: str, **engine_kwargs: Any
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Создать движок и фабрику сессий для указанного DSN."""
    engine = create_async_engine(url, **engine_kwargs)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


class LazySessionFactory:
    """Фабрика сессий с отложенной инициализацией.

    Ведёт себя как ``async_sessionmaker``: вызов возвращает ``AsyncSession``.
    Пока фабрика не сконфигурирована явно, DSN берётся из настроек.
    """

    _engine: AsyncEngine | None = None
    _factory: async_sessionmaker[AsyncSession] | None = None

    def configure(
        self,
        url: str | None = None,
        *,
        factory: async_sessionmaker[AsyncSession] | None = None,
        engine: AsyncEngine | None = None,
        **engine_kwargs: Any,
    ) -> None:
        """Задать источник сессий: DSN или готовую фабрику."""
        if factory is not None:
            self._engine = engine
            self._factory = factory
            return
        if url is None:
            msg = "Нужно передать либо url, либо factory"
            raise ValueError(msg)
        self._engine, self._factory = create_session_factory(url, **engine_kwargs)

    def reset(self) -> None:
        """Сбросить конфигурацию (следующее обращение возьмёт DSN из настроек)."""
        self._engine = None
        self._factory = None

    @property
    def is_configured(self) -> bool:
        """Сконфигурирована ли фабрика."""
        return self._factory is not None

    @property
    def factory(self) -> async_sessionmaker[AsyncSession]:
        """Фабрика сессий; создаётся при первом обращении."""
        if self._factory is None:
            from vkt_bot.config import get_settings

            self.configure(str(get_settings().db_url))
        assert self._factory is not None  # noqa: S101
        return self._factory

    @property
    def engine(self) -> AsyncEngine:
        """Движок; создаётся при первом обращении."""
        self.factory  # noqa: B018  # гарантирует инициализацию
        assert self._engine is not None  # noqa: S101
        return self._engine

    async def dispose(self) -> None:
        """Закрыть пул соединений, если движок был создан."""
        if self._engine is not None:
            await self._engine.dispose()

    def __call__(self, **kwargs: Any) -> AsyncSession:
        return self.factory(**kwargs)


async_session = LazySessionFactory()
