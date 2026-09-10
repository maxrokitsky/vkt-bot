"""``core.events``: реестр типов и ``emit``."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING
import uuid

import pytest
import structlog

from vkt_bot.core.events import Actor, EventType, emit
from vkt_bot.core.events.registry import (
    EventSpec,
    all_specs,
    fallback_spec,
    get,
    register,
)
from vkt_bot.core.models.event import (
    ActorType,
    EntityType,
    EventRecord,
    EventSeverity,
    EventSource,
)
from vkt_bot.core.repositories.event import EventRepository

from tests.factories import make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


class TestRegistry:
    """Реестр типов."""

    def test_core_types_are_registered(self) -> None:
        spec = get(EventType.ROLE_ASSIGNED)
        assert spec is not None
        assert spec.source is EventSource.PANEL

    def test_every_spec_has_a_template(self) -> None:
        assert all(spec.template for spec in all_specs())

    def test_types_are_unique(self) -> None:
        types = [spec.type for spec in all_specs()]
        assert len(types) == len(set(types))

    def test_unknown_type(self) -> None:
        assert get("nope.nothing") is None

    def test_register_is_idempotent_for_the_same_spec(self) -> None:
        spec = EventSpec(
            type="test.same",
            title="Тест",
            template="Тест",
            source=EventSource.SYSTEM,
        )
        register(spec)
        register(spec)
        assert get("test.same") == spec

    def test_conflicting_registration_raises(self) -> None:
        """Молча перетёртый тип искали бы долго."""
        base = EventSpec(
            type="test.conflict",
            title="Тест",
            template="Тест",
            source=EventSource.SYSTEM,
        )
        register(base)
        with pytest.raises(ValueError, match="test.conflict"):
            register(
                EventSpec(
                    type="test.conflict",
                    title="Другой",
                    template="Другой",
                    source=EventSource.PANEL,
                )
            )

    def test_fallback_keeps_the_identifier(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="vkt_bot.events"):
            spec = fallback_spec("plugin.unregistered")

        assert spec.type == "plugin.unregistered"
        assert "events.unknown_type" in caplog.text


class TestEmit:
    """``emit``."""

    async def test_writes_a_row(
        self, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await emit(
            session,
            EventType.ROLE_CREATED,
            actor=Actor.from_user(superuser),
            entity=(EntityType.ROLE, "role-1"),
            payload={"role": "devs"},
        )
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.type == "role.created"
        assert row.source is EventSource.PANEL
        assert row.severity is EventSeverity.INFO
        assert row.actor_type is ActorType.USER
        assert row.actor_id == superuser.id
        assert row.entity_id == "role-1"
        assert row.payload == {"role": "devs"}

    async def test_summary_is_rendered_from_the_template(
        self, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await emit(
            session,
            EventType.ROLE_CREATED,
            actor=Actor.from_user(superuser),
            payload={"role": "devs"},
        )
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.summary == f"{superuser.display_name} создал роль devs"

    async def test_missing_template_field_does_not_break(
        self, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """Забытое поле — прочерк, а не исключение посреди действия."""
        await emit(session, EventType.ROLE_CREATED, actor=Actor.from_user(superuser))
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.summary.endswith("—")

    async def test_explicit_summary_wins(
        self, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await emit(
            session,
            EventType.ROLE_CREATED,
            actor=Actor.from_user(superuser),
            summary="Своя формулировка",
        )
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.summary == "Своя формулировка"

    async def test_source_can_be_overridden(
        self, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """Роль назначают и из панели, и командой — источник разный."""
        await emit(
            session,
            EventType.ROLE_CREATED,
            actor=Actor.from_user(superuser),
            source=EventSource.COMMAND,
            payload={"role": "devs"},
        )
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.source is EventSource.COMMAND

    async def test_non_persisted_type_writes_nothing(
        self, session: AsyncSession
    ) -> None:
        result = await emit(
            session,
            EventType.MESSAGE_SENT,
            actor=Actor.bot(),
            chat_id="chat-1",
        )
        await session.commit()

        assert result is None
        assert list(await EventRepository(session).list()) == []

    async def test_non_persisted_type_still_logs(
        self, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot.events"):
            await emit(
                session, EventType.MESSAGE_SENT, actor=Actor.bot(), chat_id="chat-1"
            )

        assert "message.sent" in caplog.text

    async def test_trace_id_links_the_row_to_the_logs(
        self, session: AsyncSession
    ) -> None:
        trace = uuid.uuid4().hex
        with structlog.contextvars.bound_contextvars(trace_id=trace):
            await emit(session, EventType.ROLE_CREATED, payload={"role": "devs"})
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.trace_id == trace

    async def test_unknown_type_is_still_recorded(
        self, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Забытая регистрация не повод терять событие."""
        with caplog.at_level("WARNING", logger="vkt_bot.events"):
            await emit(session, "plugin.forgotten")
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.type == "plugin.forgotten"
        assert row.source is EventSource.SYSTEM

    async def test_payload_is_made_json_safe(self, session: AsyncSession) -> None:
        moment = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        await emit(
            session,
            EventType.ROLE_CREATED,
            payload={"when": moment, "obj": object(), "ids": {1, 2}},
        )
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.payload["when"] == moment.isoformat()
        assert isinstance(row.payload["obj"], str)
        assert sorted(row.payload["ids"]) == [1, 2]

    async def test_rollback_takes_the_event_with_it(
        self, session: AsyncSession
    ) -> None:
        """Событие не должно пережить откат действия, которое его породило."""
        await emit(session, EventType.ROLE_CREATED, payload={"role": "devs"})
        await session.rollback()

        assert list(await EventRepository(session).list()) == []

    async def test_long_summary_is_trimmed(self, session: AsyncSession) -> None:
        await emit(session, EventType.ROLE_CREATED, summary="x" * 1000)
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert len(row.summary) == 500


class TestActor:
    """Фабрики ``Actor``."""

    async def test_from_user(self, superuser: ChatUser) -> None:
        actor = Actor.from_user(superuser)
        assert actor.type is ActorType.USER
        assert actor.id == superuser.id

    def test_from_event_takes_the_name_from_the_payload(self) -> None:
        """В базе имени может ещё не быть, а в событии оно есть."""
        event = make_event("new_message")
        actor = Actor.from_event(event)

        assert actor.type is ActorType.USER
        assert actor.id == event.payload.sender.userId
        assert event.payload.sender.firstName in actor.display

    def test_from_event_without_sender(self) -> None:
        event = make_event("deleted_message")
        assert Actor.from_event(event).type is ActorType.SYSTEM

    def test_bot(self) -> None:
        assert Actor.bot().type is ActorType.BOT

    def test_system(self) -> None:
        actor = Actor.system()
        assert actor.type is ActorType.SYSTEM
        assert actor.id is None

    def test_external(self) -> None:
        actor = Actor.external("gitlab")
        assert actor.type is ActorType.EXTERNAL
        assert actor.id == "gitlab"

    async def test_default_actor_is_the_system(self, session: AsyncSession) -> None:
        await emit(session, EventType.ROLE_CREATED)
        await session.commit()

        (row,) = await EventRepository(session).list()
        assert row.actor_type is ActorType.SYSTEM


class TestSeverityGoesToTheLog:
    """Уровень записи в логе совпадает со значимостью события."""

    async def test_error_event_logs_as_error(
        self, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot.events"):
            await emit(
                session,
                EventType.MESSAGE_SEND_FAILED,
                actor=Actor.bot(),
                chat_id="chat-1",
                payload={"reason": "Chat not found"},
            )

        (record,) = [r for r in caplog.records if r.name == "vkt_bot.events"]
        assert record.levelname == "ERROR"


class TestEventRecordRepr:
    """``__repr__`` — чтобы в шелле было видно, что за строка."""

    def test_repr(self) -> None:
        record = EventRecord(id=1, type="role.created")
        assert "role.created" in repr(record)
