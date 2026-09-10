"""Чистые функции из ``vkt_bot.utils``."""

from __future__ import annotations

import datetime

import pytest

from vkt_bot.utils.datetime import localize_datetime, now
from vkt_bot.utils.message import mention


class TestMention:
    """``mention``."""

    def test_wraps_user_id(self) -> None:
        assert mention("1234567890") == "@[1234567890]"

    def test_email_like_id(self) -> None:
        assert mention("user@example.com") == "@[user@example.com]"

    def test_empty_id(self) -> None:
        assert mention("") == "@[]"


class TestLocalizeDatetime:
    """``localize_datetime``."""

    def test_recent_past_in_russian(self) -> None:
        moment = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
        assert localize_datetime(moment) == "2 часа назад"

    def test_future(self) -> None:
        moment = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=3)
        assert "через" in localize_datetime(moment)

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        moment = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        assert localize_datetime(moment) in {"только что", "сейчас"}


class TestNow:
    """``now``."""

    def test_is_broken(self) -> None:
        """Известный дефект: ``datetime.datetime()`` вызывается без аргументов."""
        with pytest.raises(TypeError):
            now()
