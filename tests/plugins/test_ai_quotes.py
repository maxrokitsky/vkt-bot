"""Разбор цитаты: кому отвечают, на что и о чём."""

from __future__ import annotations

from typing import Any

from vkteams_client.types import NewMessageEvent

from vkt_ai.quotes import QUOTE_LIMIT, quote_line, quoted, replies_to

from tests.factories import make_event

BOT_ID = "1011835311"


def event(**overrides: Any) -> NewMessageEvent:
    return make_event("new_message_reply", **overrides)  # type: ignore[return-value]


def part(**message: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "from": {"firstName": "Пётр", "lastName": "Петров", "userId": "9876543210"},
        "msgId": "6752739791872001115",
        "text": "катим в пятницу",
    }
    return {"type": "reply", "payload": {"message": base | message}}


class TestQuoted:
    """Что процитировали."""

    def test_reply_part_is_found(self) -> None:
        message = quoted(event().payload)

        assert message is not None
        assert message.msgId == "6752739791872001115"
        assert message.text == "Дежурный — Иван."

    def test_plain_message_has_no_quote(self) -> None:
        assert quoted(make_event("new_message").payload) is None  # type: ignore[union-attr]

    def test_forward_is_not_a_reply(self) -> None:
        """Переслать сообщение в чат — не то же, что обратиться к боту."""
        forwarded = part()
        forwarded["type"] = "forward"

        assert quoted(event(parts=[forwarded]).payload) is None


class TestRepliesTo:
    """Кому отвечают."""

    def test_our_message(self) -> None:
        assert replies_to(event().payload, BOT_ID) is True

    def test_someone_else(self) -> None:
        assert replies_to(event(parts=[part()]).payload, BOT_ID) is False

    def test_without_our_id_nothing_matches(self) -> None:
        """Бот не спросил у API, как его зовут, — сравнивать не с чем."""
        assert replies_to(event().payload, None) is False

    def test_quote_without_a_sender(self) -> None:
        quote = part()
        quote["payload"]["message"].pop("from")

        assert replies_to(event(parts=[quote]).payload, BOT_ID) is False


class TestQuoteLine:
    """Цитата для промпта."""

    def test_name_and_text(self) -> None:
        message = quoted(event(parts=[part()]).payload)

        assert message is not None
        assert quote_line(message) == "Пётр Петров: катим в пятницу"

    def test_empty_text_gives_nothing(self) -> None:
        """Вложение без подписи описывать нечем."""
        message = quoted(event(parts=[part(text="")]).payload)

        assert message is not None
        assert quote_line(message) is None

    def test_long_quote_is_trimmed(self) -> None:
        """Начало реплики обычно и несёт смысл."""
        message = quoted(event(parts=[part(text="а" * (QUOTE_LIMIT + 100))]).payload)

        assert message is not None
        line = quote_line(message)
        assert line is not None
        assert line.endswith("…")
        assert len(line) < QUOTE_LIMIT + 100
