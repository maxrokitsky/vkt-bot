"""``Query`` / ``QueryResult`` — композиция и пагинация."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry
from vkt_bot.core.models.role import Role
from vkt_bot.core.queries.chat import ChatByIdQuery
from vkt_bot.core.queries.log_entry import (
    FilterByActionType,
    FilterByActorId,
    FilterByActorType,
    FilterByDateRange,
    FilterByEntityId,
    FilterByEntityType,
    OrderByTimestamp,
    SearchByDescription,
)
from vkt_bot.core.queries.roles import (
    RoleAssignmentByUserAndRoleQuery,
    RoleByIdQuery,
    RoleByUserQuery,
)
from vkt_bot.core.queries.user import ChatUserHasRoleQuery
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.core.repositories.log_entry import LogEntryRepository
from vkt_bot.core.repositories.role import RoleAssignmentRepository, RoleRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.db.query import Page

from tests.factories import assign_role, create_chat, create_chat_user, create_role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def roles(session: AsyncSession) -> list[Role]:
    """Три роли: admin, devs, qa."""
    return [await create_role(session, name) for name in ("admin", "devs", "qa")]


class TestQueryResult:
    """Методы ``QueryResult``."""

    async def test_list(self, session: AsyncSession, roles: list[Role]) -> None:
        result = await RoleRepository(session).query().list()
        assert {r.name for r in result} == {"admin", "devs", "qa"}

    async def test_list_empty(self, session: AsyncSession) -> None:
        assert list(await RoleRepository(session).query().list()) == []

    async def test_one_or_none_found(self, session: AsyncSession) -> None:
        await create_chat(session, "chat-1")
        chat = (
            await ChatRepository(session)
            .query(ChatByIdQuery(chat_id="chat-1"))
            .one_or_none()
        )
        assert chat is not None
        assert chat.id == "chat-1"

    async def test_one_or_none_missing(self, session: AsyncSession) -> None:
        result = (
            await ChatRepository(session)
            .query(ChatByIdQuery(chat_id="nope"))
            .one_or_none()
        )
        assert result is None

    async def test_one_raises_when_missing(self, session: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await ChatRepository(session).query(ChatByIdQuery(chat_id="nope")).one()

    async def test_one_returns_row(self, session: AsyncSession) -> None:
        await create_chat(session, "chat-2")
        chat = (
            await ChatRepository(session).query(ChatByIdQuery(chat_id="chat-2")).one()
        )
        assert chat.id == "chat-2"

    async def test_exists(self, session: AsyncSession) -> None:
        await create_chat(session, "chat-3")
        query = ChatRepository(session).query(ChatByIdQuery(chat_id="chat-3"))
        assert await query.exists() is True

    async def test_exists_false(self, session: AsyncSession) -> None:
        query = ChatRepository(session).query(ChatByIdQuery(chat_id="nope"))
        assert await query.exists() is False


class TestQueryComposition:
    """Композиция нескольких ``Query``."""

    async def test_empty_query_returns_everything(
        self, session: AsyncSession, roles: list[Role]
    ) -> None:
        assert len(await RoleRepository(session).query().list()) == len(roles)

    async def test_optional_filter_is_skipped_when_none(
        self, session: AsyncSession, roles: list[Role]
    ) -> None:
        result = await RoleRepository(session).query(RoleByIdQuery()).list()
        assert len(result) == len(roles)

    async def test_role_by_id_query_needs_postgres(
        self, session: AsyncSession, roles: list[Role], is_postgres: bool
    ) -> None:
        """``RoleByIdQuery.role_id`` объявлен как ``str``, а колонка — ``UUID``.

        PostgreSQL приводит строку сам, SQLite падает. Расхождение типов
        стоит убрать (ROADMAP 3.9), пока фиксируем как есть.
        """
        query = RoleRepository(session).query(RoleByIdQuery(role_id=str(roles[0].id)))
        if is_postgres:
            role = await query.one()
            assert role.name == "admin"
        else:
            with pytest.raises(Exception, match="hex"):
                await query.one_or_none()

    async def test_two_queries_are_both_applied(self, session: AsyncSession) -> None:
        user = await create_chat_user(session, "u@example.com")
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        assignments = (
            await RoleAssignmentRepository(session)
            .query(
                RoleAssignmentByUserAndRoleQuery(user_id=user.id),
                RoleAssignmentByUserAndRoleQuery(role_id=role.id),
            )
            .list()
        )
        assert len(assignments) == 1

    async def test_filters_narrow_the_result(self, session: AsyncSession) -> None:
        user = await create_chat_user(session, "u@example.com")
        role = await create_role(session, "devs")
        other = await create_role(session, "qa")
        await assign_role(session, user.id, role.id)

        assignments = (
            await RoleAssignmentRepository(session)
            .query(RoleAssignmentByUserAndRoleQuery(user_id=user.id, role_id=other.id))
            .list()
        )
        assert list(assignments) == []

    async def test_join_query(self, session: AsyncSession) -> None:
        user = await create_chat_user(session, "u@example.com")
        role = await create_role(session, "devs")
        await create_role(session, "qa")
        await assign_role(session, user.id, role.id)

        user_roles = (
            await RoleRepository(session).query(RoleByUserQuery(user_id=user.id)).list()
        )
        assert [r.name for r in user_roles] == ["devs"]

    async def test_has_role_query_is_case_insensitive(
        self, session: AsyncSession
    ) -> None:
        user = await create_chat_user(session, "u@example.com")
        role = await create_role(session, "DevOps")
        await assign_role(session, user.id, role.id)

        users = (
            await ChatUserRepository(session)
            .query(ChatUserHasRoleQuery(roles=["devops"]))
            .list()
        )
        assert [u.id for u in users] == [user.id]

    async def test_chat_by_id_query(self, session: AsyncSession) -> None:
        await create_chat(session, "chat-1")
        await create_chat(session, "chat-2")

        chats = (
            await ChatRepository(session).query(ChatByIdQuery(chat_id="chat-2")).list()
        )
        assert [c.id for c in chats] == ["chat-2"]

    async def test_query_does_not_mutate_the_repository(
        self, session: AsyncSession, roles: list[Role]
    ) -> None:
        repo = RoleRepository(session)
        await repo.query(RoleByUserQuery(user_id="nobody@example.com")).list()
        assert len(await repo.query().list()) == len(roles)


class TestPagination:
    """``QueryResult.paginate``."""

    @pytest.fixture
    async def log_entries(self, session: AsyncSession) -> list[LogEntry]:
        entries = []
        base = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        for i in range(7):
            entry = LogEntry(
                timestamp=base + datetime.timedelta(hours=i),
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                action_type=ActionType.CREATE,
                entity_type=EntityType.ROLE,
                entity_id=f"role-{i}",
                description=f"Создана роль {i}",
            )
            session.add(entry)
            entries.append(entry)
        await session.commit()
        return entries

    async def test_first_page(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = await LogEntryRepository(session).query().paginate(page=1, size=3)

        assert isinstance(page, Page)
        assert page.total == len(log_entries)
        assert page.page == 1
        assert len(page.results) == 3

    async def test_second_page(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = await LogEntryRepository(session).query().paginate(page=3, size=3)
        assert len(page.results) == 1

    async def test_page_below_one_is_clamped(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = await LogEntryRepository(session).query().paginate(page=0, size=3)
        assert page.page == 1

    async def test_page_above_max_is_clamped(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = await LogEntryRepository(session).query().paginate(page=99, size=3)
        assert page.page == 3
        assert len(page.results) == 1

    async def test_empty_table_gives_page_one(self, session: AsyncSession) -> None:
        page = await LogEntryRepository(session).query().paginate(page=5, size=10)
        assert (page.total, page.page, page.results) == (0, 1, [])

    async def test_ordering_is_applied(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = (
            await LogEntryRepository(session)
            .query(OrderByTimestamp(descending=True))
            .paginate(page=1, size=2)
        )
        assert [e.entity_id for e in page.results] == ["role-6", "role-5"]

    async def test_ascending_ordering(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        page = (
            await LogEntryRepository(session)
            .query(OrderByTimestamp(descending=False))
            .paginate(page=1, size=2)
        )
        assert [e.entity_id for e in page.results] == ["role-0", "role-1"]

    async def test_total_ignores_filters(
        self, session: AsyncSession, log_entries: list[LogEntry]
    ) -> None:
        """Известное поведение: ``total`` считается по таблице, не по фильтру.

        ``paginate`` берёт ``statement.froms[0]``, поэтому ``where`` в подсчёт
        не попадает — итог расходится с реальным числом строк.
        """
        page = (
            await LogEntryRepository(session)
            .query(FilterByEntityId(entity_id="role-1"))
            .paginate(page=1, size=10)
        )
        assert len(page.results) == 1
        assert page.total == len(log_entries)


class TestLogEntryQueries:
    """Фильтры логов."""

    @pytest.fixture
    async def entries(self, session: AsyncSession) -> None:
        rows = [
            LogEntry(
                timestamp=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                actor_type=ActorType.WEB_USER,
                actor_id="admin@example.com",
                action_type=ActionType.CREATE,
                entity_type=EntityType.ROLE,
                entity_id="role-1",
                description="Создана роль devs",
            ),
            LogEntry(
                timestamp=datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC),
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                action_type=ActionType.DELETE,
                entity_type=EntityType.CHAT_USER,
                entity_id="user-1",
                description="Удалён пользователь",
            ),
        ]
        session.add_all(rows)
        await session.commit()

    async def test_filter_by_actor_type(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(FilterByActorType(actor_type=ActorType.SYSTEM))
            .list()
        )
        assert [e.entity_id for e in result] == ["user-1"]

    async def test_filter_by_actor_id(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(FilterByActorId(actor_id="admin@example.com"))
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_filter_by_action_type(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(FilterByActionType(action_type=ActionType.DELETE))
            .list()
        )
        assert [e.entity_id for e in result] == ["user-1"]

    async def test_filter_by_entity_type(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(FilterByEntityType(entity_type=EntityType.ROLE))
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_search_by_description_matches_substring(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(SearchByDescription(search_query="роль devs"))
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_search_by_description_is_case_insensitive(
        self, session: AsyncSession, entries: None, is_postgres: bool
    ) -> None:
        """``ilike`` игнорирует регистр; для кириллицы это требует PostgreSQL."""
        if not is_postgres:
            pytest.skip("SQLite не приводит регистр кириллицы в LIKE")
        result = (
            await LogEntryRepository(session)
            .query(SearchByDescription(search_query="СОЗДАНА РОЛЬ"))
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_date_range_start_only(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(
                FilterByDateRange(
                    start_date=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC)
                )
            )
            .list()
        )
        assert [e.entity_id for e in result] == ["user-1"]

    async def test_date_range_end_only(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(
                FilterByDateRange(
                    end_date=datetime.datetime(2026, 1, 15, tzinfo=datetime.UTC)
                )
            )
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_empty_date_range_matches_everything(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = await LogEntryRepository(session).query(FilterByDateRange()).list()
        assert len(result) == 2

    async def test_combined_filters(self, session: AsyncSession, entries: None) -> None:
        result = (
            await LogEntryRepository(session)
            .query(
                FilterByActorType(actor_type=ActorType.WEB_USER),
                FilterByEntityType(entity_type=EntityType.ROLE),
                OrderByTimestamp(),
            )
            .list()
        )
        assert [e.entity_id for e in result] == ["role-1"]

    async def test_contradictory_filters_return_nothing(
        self, session: AsyncSession, entries: None
    ) -> None:
        result = (
            await LogEntryRepository(session)
            .query(
                FilterByActorType(actor_type=ActorType.SYSTEM),
                FilterByEntityType(entity_type=EntityType.ROLE),
            )
            .list()
        )
        assert list(result) == []


class TestQueryProtocol:
    """Собственные реализации ``Query``."""

    async def test_custom_query(self, session: AsyncSession) -> None:
        from vkt_bot.db.query import Query

        class NameStartsWith(Query):
            prefix: str

            def apply(self, statement: Any) -> Any:  # noqa: ANN401
                return statement.where(Role.name.startswith(self.prefix))

        await create_role(session, "devs")
        await create_role(session, "qa")

        result = await RoleRepository(session).query(NameStartsWith(prefix="de")).list()
        assert [r.name for r in result] == ["devs"]

    def test_base_query_apply_returns_none(self) -> None:
        """У протокола ``Query.apply`` — пустое тело."""
        from vkt_bot.db.query import Query

        assert Query().apply(sa.select(Role)) is None
