"""Определение обращения к боту по упоминанию."""

from __future__ import annotations

import pytest

from vkt_ai.mentions import by_id, mentions_bot, spans_of, strip_mention

BOT_ID = "1011835311"
NICK = "max_test_bot"


def call(text: str) -> bool:
    return mentions_bot(text, user_id=BOT_ID, nick=NICK)


def clean(text: str) -> str:
    return strip_mention(text, user_id=BOT_ID, nick=NICK)


class TestDetect:
    """``mentions_bot``."""

    @pytest.mark.parametrize(
        "text",
        [
            f"@[{BOT_ID}] кто дежурный?",
            f"кто дежурный, @[{BOT_ID}]?",
            f"@{NICK} кто дежурный?",
            f"@{NICK}, кто дежурный?",
            f"эй @{NICK} проснись",
            # Регистр в нике человек не соблюдает.
            f"@{NICK.upper()} привет",
        ],
    )
    def test_addressed(self, text: str) -> None:
        assert call(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "просто сообщение",
            "@[9999999999] кто дежурный?",
            "@другой_бот привет",
            # Ник соседа начинается так же — это не мы.
            f"@{NICK}2 привет",
            f"@{NICK}_dev привет",
            "",
        ],
    )
    def test_not_addressed(self, text: str) -> None:
        assert call(text) is False

    def test_without_identity_nothing_matches(self) -> None:
        """До старта бот не знает, как его зовут, — сравнивать не с чем."""
        assert mentions_bot(f"@[{BOT_ID}] привет", user_id=None, nick=None) is False

    def test_id_only(self) -> None:
        assert mentions_bot(f"@[{BOT_ID}] привет", user_id=BOT_ID) is True


class TestStrip:
    """``strip_mention``."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (f"@[{BOT_ID}] кто дежурный?", "кто дежурный?"),
            (f"@[{BOT_ID}], кто дежурный?", "кто дежурный?"),
            (f"@[{BOT_ID}]: кто дежурный?", "кто дежурный?"),
            (f"@{NICK} кто дежурный?", "кто дежурный?"),
            (f"@{NICK}, кто дежурный?", "кто дежурный?"),
            (f"кто дежурный, @{NICK}?", "кто дежурный, ?"),
            # Обращение без вопроса — пусто, и хендлер покажет справку.
            (f"@[{BOT_ID}]", ""),
            (f"@{NICK}", ""),
        ],
    )
    def test_removes_the_address(self, text: str, expected: str) -> None:
        assert clean(text) == expected

    def test_other_mentions_survive(self) -> None:
        """Упоминание коллеги — часть вопроса, а не обращение к боту."""
        assert clean(f"@[{BOT_ID}] в каких чатах @[9876543210]?") == (
            "в каких чатах @[9876543210]?"
        )

    def test_plain_text_is_untouched(self) -> None:
        assert clean("кто дежурный?") == "кто дежурный?"

    def test_by_id_format(self) -> None:
        assert by_id(BOT_ID) == f"@[{BOT_ID}]"


class Part:
    """Отрезок разметки: у клиента это ``FormatPart``."""

    def __init__(self, offset: int, length: int) -> None:
        self.offset = offset
        self.length = length


class TestSpans:
    """Опознание через разметку ``format.mention``.

    Главная страховка: она не зависит от того, как сервер отрисовал
    упоминание в тексте — идентификатором, ником или именем человека.
    """

    def test_extracts_mention_spans(self) -> None:
        assert spans_of({"mention": [Part(0, 5)], "bold": [Part(6, 2)]}) == [(0, 5)]

    def test_no_format(self) -> None:
        assert spans_of(None) == []
        assert spans_of({}) == []
        assert spans_of({"bold": [Part(0, 2)]}) == []

    def test_broken_part_is_skipped(self) -> None:
        """Разметка приходит от сервера — падать на ней нельзя."""
        assert spans_of({"mention": [Part(0, 0), object()]}) == []

    def test_display_name_rendering(self) -> None:
        """Если упоминание отрисовано именем, а не `@[id]`, — тоже наше."""
        text = "Бот Ассистент, кто дежурный?"

        assert (
            mentions_bot(
                text,
                user_id=BOT_ID,
                nick=NICK,
                first_name="Бот",
                spans=[(0, 13)],
            )
            is True
        )

    def test_similar_name_is_not_ours(self) -> None:
        """У бота имя «Бот» — участник «Боталов» не должен считаться им."""
        text = "Боталов Иван, посмотри"

        assert (
            mentions_bot(
                text, user_id=BOT_ID, nick=NICK, first_name="Бот", spans=[(0, 12)]
            )
            is False
        )

    def test_span_of_someone_else(self) -> None:
        text = "Пётр Петров, посмотри"

        assert (
            mentions_bot(
                text, user_id=BOT_ID, nick=NICK, first_name="Бот", spans=[(0, 11)]
            )
            is False
        )

    def test_exact_ids_win_over_the_name(self) -> None:
        """Упомянули тёзку бота — значит, не бота.

        Разметка опознаёт по имени, и оно грубое: если точные
        идентификаторы пришли и нас среди них нет, гадать поверх нельзя.
        """
        text = "Бот Петров, посмотри"

        assert (
            mentions_bot(
                text,
                user_id=BOT_ID,
                nick=NICK,
                first_name="Бот",
                spans=[(0, 10)],
                mentioned_ids=["987"],
            )
            is False
        )

    def test_exact_id_of_the_bot_matches(self) -> None:
        assert (
            mentions_bot(
                "кто угодно", user_id=BOT_ID, nick=NICK, mentioned_ids=[BOT_ID]
            )
            is True
        )

    def test_typed_nick_works_next_to_someone_elses_mention(self) -> None:
        """Ник напечатали руками — части для него нет, а текст остался."""
        assert (
            mentions_bot(
                f"@[987] эй @{NICK} посмотри",
                user_id=BOT_ID,
                nick=NICK,
                mentioned_ids=["987"],
            )
            is True
        )

    def test_span_is_cut_from_the_question(self) -> None:
        text = "Бот Ассистент, кто дежурный?"

        assert (
            strip_mention(
                text, user_id=BOT_ID, nick=NICK, first_name="Бот", spans=[(0, 13)]
            )
            == "кто дежурный?"
        )

    def test_several_spans_are_cut_from_the_end(self) -> None:
        """Вырезание с начала сдвинуло бы смещения остальных отрезков."""
        text = "Бот, скажи Бот"

        assert (
            strip_mention(
                text, user_id=None, nick=None, first_name="Бот", spans=[(0, 3), (11, 3)]
            )
            == "скажи"
        )
