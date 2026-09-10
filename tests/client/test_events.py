"""Парсинг ответа ``/events/get``."""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

import pytest
from vkteams_client.enums import ChatType, EventType
from vkteams_client.enums import PayLoadFileType
from vkteams_client.types import (
    Bot,
    CallbackQueryEvent,
    ChangedChatInfoEvent,
    DeletedMessageEvent,
    EditedMessageEvent,
    EventsResponse,
    LeftChatMembersEvent,
    NewChatMembersEvent,
    NewMessageEvent,
    PinnedMessageEvent,
    UnpinnedMessageEvent,
    User,
)

from tests.client.conftest import query_of, url_for
from tests.factories import ALL_EVENT_FIXTURES, events_response, make_event, raw_event

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

EVENT_CLASSES = {
    "new_message": NewMessageEvent,
    "edited_message": EditedMessageEvent,
    "deleted_message": DeletedMessageEvent,
    "pinned_message": PinnedMessageEvent,
    "unpinned_message": UnpinnedMessageEvent,
    "new_chat_members": NewChatMembersEvent,
    "left_chat_members": LeftChatMembersEvent,
    "changed_chat_info": ChangedChatInfoEvent,
    "callback_query": CallbackQueryEvent,
}


class TestDiscriminator:
    """Дискриминатор ``type`` выбирает правильный класс события."""

    @pytest.mark.parametrize(("fixture", "expected"), EVENT_CLASSES.items())
    def test_type_resolves_to_class(self, fixture: str, expected: type) -> None:
        event = make_event(fixture)
        assert isinstance(event, expected)

    @pytest.mark.parametrize("fixture", ALL_EVENT_FIXTURES)
    def test_every_fixture_parses(self, fixture: str) -> None:
        event = make_event(fixture)
        assert event.eventId == raw_event(fixture)["eventId"]

    def test_all_nine_event_types_covered(self) -> None:
        assert set(EVENT_CLASSES) == {
            name for name in EVENT_CLASSES if name in ALL_EVENT_FIXTURES
        }
        assert len(EVENT_CLASSES) == len(EventType)

    def test_unknown_type_is_rejected(self) -> None:
        from pydantic import ValidationError

        data = raw_event("new_message")
        data["type"] = "somethingNew"
        with pytest.raises(ValidationError):
            EventsResponse.model_validate({"ok": True, "events": [data]})


class TestNewMessagePayload:
    """Полезная нагрузка ``newMessage``."""

    def test_sender_is_read_from_alias_from(self) -> None:
        event = make_event("new_message")
        assert isinstance(event.payload.sender, User)
        assert event.payload.sender.userId == "1234567890"
        assert event.payload.sender.firstName == "Иван"

    def test_bot_sender_parses_as_bot(self) -> None:
        event = make_event("new_message_from_bot")
        assert isinstance(event.payload.sender, Bot)
        assert event.payload.sender.nick == "test_bot"

    def test_sender_field_name_is_not_accepted(self) -> None:
        """Модель принимает только ``from``: ``sender`` не альтернативное имя."""
        from pydantic import ValidationError

        data = raw_event("new_message")
        data["payload"]["sender"] = data["payload"].pop("from")
        with pytest.raises(ValidationError):
            NewMessageEvent.model_validate(data)

    def test_timestamp_becomes_datetime(self) -> None:
        event = make_event("new_message")
        assert isinstance(event.payload.timestamp, datetime.datetime)
        assert event.payload.timestamp == datetime.datetime.fromtimestamp(
            raw_event("new_message")["payload"]["timestamp"], tz=datetime.UTC
        )

    def test_chat_type_becomes_enum(self) -> None:
        assert make_event("new_message").payload.chat.type is ChatType.GROUP
        assert make_event("new_message_private").payload.chat.type is ChatType.PRIVATE

    def test_text_is_optional(self) -> None:
        data = raw_event("new_message")
        del data["payload"]["text"]
        assert NewMessageEvent.model_validate(data).payload.text is None

    def test_format_defaults_to_empty_dict(self) -> None:
        assert make_event("new_message").payload.format == {}

    def test_format_parts_are_parsed(self) -> None:
        payload = make_event("new_message_with_format").payload
        assert set(payload.format) == {"bold", "italic"}
        bold = payload.format["bold"][0]
        assert (bold.offset, bold.length) == (0, 6)

    def test_message_without_parts(self) -> None:
        assert make_event("new_message").payload.parts == []


class TestParts:
    """Вложения, упоминания, пересылки и ответы.

    Долго не разбирались вовсе (ROADMAP 3.1): в модели не было поля
    ``parts``, из-за чего терялись и вложения, и единственный источник
    ``userId`` у упоминания.
    """

    def test_file_and_mention_are_parsed(self) -> None:
        payload = make_event("new_message_with_parts").payload

        assert [part.type for part in payload.parts] == ["file", "mention"]

    def test_file_payload(self) -> None:
        file = make_event("new_message_with_parts").payload.files[0]

        assert file.fileId == "0dC76vcKS3XZOtG5DVs9y15d1daefa1ae"
        assert file.type is PayLoadFileType.IMAGE
        assert file.caption == "Картинка"

    def test_mention_carries_user_id(self) -> None:
        """Разметка ``format.mention`` несёт только смещение и длину."""
        mention = make_event("new_message_with_parts").payload.mentions[0]

        assert mention.userId == "9876543210"
        assert mention.firstName == "Пётр"

    def test_document_without_media_type(self) -> None:
        """У обычного документа ``type`` не приходит — только у медиа."""
        event = make_event(
            "new_message_with_parts",
            parts=[{"type": "file", "payload": {"fileId": "abc"}}],
        )

        assert event.payload.files[0].type is None

    @pytest.mark.parametrize(
        ("kind", "part"),
        [
            ("sticker", {"type": "sticker", "payload": {"fileId": "s1"}}),
            ("voice", {"type": "voice", "payload": {"fileId": "v1"}}),
        ],
    )
    def test_file_id_parts(self, kind: str, part: dict) -> None:
        payload = make_event("new_message_with_parts", parts=[part]).payload

        assert payload.parts[0].type == kind
        assert payload.parts[0].payload.fileId == part["payload"]["fileId"]

    @pytest.mark.parametrize("kind", ["forward", "reply"])
    def test_quoted_message(self, kind: str) -> None:
        payload = make_event(
            "new_message_with_parts",
            parts=[
                {
                    "type": kind,
                    "payload": {
                        "message": {
                            "from": {
                                "firstName": "Пётр",
                                "lastName": "Петров",
                                "userId": "9876543210",
                            },
                            "msgId": "6724238139063271643",
                            "text": "исходный текст",
                            "timestamp": 1565608694,
                        }
                    },
                }
            ],
        ).payload

        quoted = payload.parts[0].payload.message
        assert quoted.text == "исходный текст"
        assert quoted.sender is not None
        assert quoted.sender.userId == "9876543210"

    def test_unknown_part_does_not_break_the_event(self) -> None:
        """Новый тип части не должен делать сообщение нечитаемым целиком.

        Иначе бот молчал бы вместо того, чтобы ответить на остальное.
        """
        event = make_event(
            "new_message_with_parts",
            parts=[
                {"type": "mention", "payload": {"userId": "9876543210"}},
                {"type": "quantum_hologram", "payload": {"whatever": 1}},
            ],
        )

        assert [part.type for part in event.payload.parts] == [
            "mention",
            "quantum_hologram",
        ]
        assert event.payload.parts[1].payload == {"whatever": 1}
        # Известные части при этом разобраны как обычно.
        assert event.payload.mentions[0].userId == "9876543210"

    def test_edited_message_keeps_parts(self) -> None:
        """``EditedMessagePayload`` наследует поле — правка вложения не теряет его."""
        event = make_event(
            "edited_message",
            parts=[{"type": "file", "payload": {"fileId": "abc", "type": "image"}}],
        )

        assert event.payload.files[0].fileId == "abc"


class TestOtherPayloads:
    """Остальные события."""

    def test_edited_message_has_edited_timestamp(self) -> None:
        payload = make_event("edited_message").payload
        assert payload.editedTimestamp > payload.timestamp

    def test_new_chat_members(self) -> None:
        payload = make_event("new_chat_members").payload
        assert [m.userId for m in payload.newMembers] == ["9876543210"]
        assert payload.addedBy is not None
        assert payload.addedBy.userId == "1234567890"

    def test_new_chat_members_added_by_is_optional(self) -> None:
        data = raw_event("new_chat_members")
        del data["payload"]["addedBy"]
        assert NewChatMembersEvent.model_validate(data).payload.addedBy is None

    def test_callback_query(self) -> None:
        payload = make_event("callback_query").payload
        assert payload.queryId == "SVR:123456"
        assert payload.sender.userId == "1234567890"
        assert payload.message.chat.chatId == "681869378@chat.agent"
        assert json.loads(payload.callbackData)["command"] == "start__showcommands"

    def test_left_chat_members(self) -> None:
        payload = make_event("left_chat_members").payload
        assert payload.chat.chatId == "681869378@chat.agent"
        assert [m.userId for m in payload.leftMembers] == ["9876543210"]
        assert payload.removedBy is not None
        assert payload.removedBy.userId == "1234567890"

    def test_left_chat_members_removed_by_is_optional(self) -> None:
        data = raw_event("left_chat_members")
        del data["payload"]["removedBy"]
        assert LeftChatMembersEvent.model_validate(data).payload.removedBy is None

    def test_left_chat_members_without_members(self) -> None:
        """Состав может не прийти — событие всё равно должно разбираться."""
        data = raw_event("left_chat_members")
        del data["payload"]["leftMembers"]
        assert LeftChatMembersEvent.model_validate(data).payload.leftMembers == []

    def test_changed_chat_info(self) -> None:
        payload = make_event("changed_chat_info").payload
        assert payload.chat.chatId == "681869378@chat.agent"
        assert payload.title == "Новое название"

    def test_changed_chat_info_title_is_optional(self) -> None:
        data = raw_event("changed_chat_info")
        del data["payload"]["title"]
        assert ChangedChatInfoEvent.model_validate(data).payload.title is None

    @pytest.mark.parametrize(
        "fixture",
        [
            "pinned_message",
            "unpinned_message",
        ],
    )
    def test_untyped_payloads_stay_dicts(self, fixture: str) -> None:
        """У двух событий ``payload: Any`` — см. ROADMAP 3.5."""
        event = make_event(fixture)
        assert isinstance(event.payload, dict)
        assert event.payload == raw_event(fixture)["payload"]

    def test_deleted_message_payload_is_typed(self) -> None:
        """История сообщений помечает удалённые — ей нужен ``msgId``."""
        event = make_event("deleted_message")

        assert event.payload.msgId == "6752739791872001111"
        assert event.payload.chat.chatId == "681869378@chat.agent"


class TestEventStr:
    """``__str__`` события."""

    def test_new_message_str_includes_chat(self) -> None:
        event = make_event("new_message")
        assert str(event) == (
            "1 (type: newMessage, chatId: 681869378@chat.agent, "
            "msgId: 6752739791872001111)"
        )

    def test_base_event_str(self) -> None:
        event = make_event("deleted_message")
        assert str(event) == "7 (type: deletedMessage)"


class TestIsinstance:
    """Хелпер ``BaseEvent.isinstance``."""

    def test_true_for_own_class(self) -> None:
        assert NewMessageEvent.isinstance(make_event("new_message"))

    def test_false_for_other_class(self) -> None:
        assert not NewMessageEvent.isinstance(make_event("callback_query"))


class TestGetEvents:
    """HTTP-слой ``get_events``."""

    async def test_request_params(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(url_for("/events/get"), payload={"ok": True, "events": []})
        await vkteams.get_events(last_event_id=42, poll_time=20)

        params = query_of(mock_api, "/bot/v1/events/get")
        assert params["token"] == [vkteams.token]
        assert params["lastEventId"] == ["42"]
        assert params["pollTime"] == ["20"]

    async def test_parses_all_events(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/events/get"),
            payload=events_response(*ALL_EVENT_FIXTURES),
        )
        response = await vkteams.get_events(last_event_id=0, poll_time=1)

        assert response.ok
        assert len(response.events) == len(ALL_EVENT_FIXTURES)

    async def test_empty_events(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        mock_api.get(url_for("/events/get"), payload={"ok": True, "events": []})
        response = await vkteams.get_events(last_event_id=0, poll_time=1)
        assert response.events == []

    async def test_invalid_json_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/events/get"), body="not a json")
        with pytest.raises(ValidationError):
            await vkteams.get_events(last_event_id=0, poll_time=1)

    async def test_missing_events_key_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/events/get"), payload={"ok": False})
        with pytest.raises(ValidationError):
            await vkteams.get_events(last_event_id=0, poll_time=1)

    async def test_http_error_body_is_still_parsed(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Клиент не смотрит на статус: решает валидность тела."""
        mock_api.get(
            url_for("/events/get"), status=500, payload={"ok": False, "events": []}
        )
        response = await vkteams.get_events(last_event_id=0, poll_time=1)
        assert response.ok is False

    async def test_events_are_logged(
        self,
        vkteams: VKTeams,
        mock_api: aioresponses,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_api.get(url_for("/events/get"), payload=events_response("new_message"))
        with caplog.at_level("INFO", logger="vkteams_client.events"):
            await vkteams.get_events(last_event_id=0, poll_time=1)
        assert any(
            "api.event_received" in record.getMessage()
            and "newMessage" in record.getMessage()
            for record in caplog.records
        )
