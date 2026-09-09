"""``vkt_bot.db.session`` — фабрика сессий."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from vkt_bot.db.session import (
    LazySessionFactory,
    async_session,
    create_session_factory,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class TestCreateSessionFactory:
    """``create_session_factory``."""

    async def test_returns_engine_and_factory(self) -> None:
        engine, factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        try:
            assert isinstance(engine, AsyncEngine)
            assert isinstance(factory, async_sessionmaker)
        finally:
            await engine.dispose()

    async def test_sessions_do_not_expire_on_commit(self) -> None:
        engine, factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        try:
            assert factory.kw["expire_on_commit"] is False
        finally:
            await engine.dispose()

    async def test_engine_kwargs_are_forwarded(self) -> None:
        engine, _ = create_session_factory("sqlite+aiosqlite:///:memory:", echo=True)
        try:
            assert engine.echo is True
        finally:
            await engine.dispose()

    async def test_uses_the_given_url(self) -> None:
        engine, _ = create_session_factory("sqlite+aiosqlite:///:memory:")
        try:
            assert engine.url.drivername == "sqlite+aiosqlite"
        finally:
            await engine.dispose()


class TestLazySessionFactory:
    """``LazySessionFactory``."""

    @pytest.fixture
    async def factory(self) -> AsyncIterator[LazySessionFactory]:
        instance = LazySessionFactory()
        try:
            yield instance
        finally:
            await instance.dispose()

    def test_starts_unconfigured(self, factory: LazySessionFactory) -> None:
        assert factory.is_configured is False

    async def test_configure_with_url(self, factory: LazySessionFactory) -> None:
        factory.configure("sqlite+aiosqlite:///:memory:")

        assert factory.is_configured is True
        assert isinstance(factory(), AsyncSession)

    async def test_configure_with_factory(self, factory: LazySessionFactory) -> None:
        engine, sessionmaker = create_session_factory("sqlite+aiosqlite:///:memory:")
        try:
            factory.configure(factory=sessionmaker, engine=engine)
            assert factory.factory is sessionmaker
            assert factory.engine is engine
        finally:
            await engine.dispose()

    def test_configure_without_arguments_raises(
        self, factory: LazySessionFactory
    ) -> None:
        with pytest.raises(ValueError, match="url"):
            factory.configure()

    async def test_reset_drops_configuration(self, factory: LazySessionFactory) -> None:
        factory.configure("sqlite+aiosqlite:///:memory:")
        await factory.dispose()
        factory.reset()

        assert factory.is_configured is False

    async def test_factory_is_reused(self, factory: LazySessionFactory) -> None:
        factory.configure("sqlite+aiosqlite:///:memory:")
        assert factory.factory is factory.factory

    async def test_call_passes_kwargs(self, factory: LazySessionFactory) -> None:
        factory.configure("sqlite+aiosqlite:///:memory:")
        session = factory(autoflush=False)
        try:
            assert session.autoflush is False
        finally:
            await session.close()

    async def test_dispose_without_engine_is_safe(self) -> None:
        await LazySessionFactory().dispose()

    def test_falls_back_to_settings_dsn(self, factory: LazySessionFactory) -> None:
        """Без явной конфигурации DSN берётся из настроек."""
        from vkt_bot.config import get_settings

        assert factory.factory is not None
        assert factory.engine.url.render_as_string(hide_password=False) == str(
            get_settings().db_url.unicode_string()
        )


class TestModuleLevelFactory:
    """Глобальный ``async_session``."""

    def test_is_a_lazy_factory(self) -> None:
        assert isinstance(async_session, LazySessionFactory)

    def test_is_configured_by_the_test_fixture(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        assert async_session.is_configured is True
        assert async_session.factory is session_factory

    async def test_handlers_see_the_test_database(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Модули, импортировавшие ``async_session``, работают с той же базой."""
        from vkt_bot.core.handlers import chats

        assert chats.async_session is async_session
        async with chats.async_session() as handler_session:
            assert handler_session.bind is session_factory.kw["bind"]
