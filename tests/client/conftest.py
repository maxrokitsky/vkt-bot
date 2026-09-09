"""Фикстуры для тестов ``vkteams_client``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

import pytest
from aioresponses import aioresponses

from vkteams_client import VKTeams

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

TOKEN = "001.0000000000.0000000000:000000000"
BASE_URL = "https://myteam.mail.ru/bot/v1"

ANY_URL = re.compile(r".*")


@pytest.fixture
async def vkteams() -> AsyncIterator[VKTeams]:
    """Клиент VK Teams с закрытием сессии после теста."""
    client = VKTeams(TOKEN)
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def mock_api() -> Iterator[aioresponses]:
    """Мок HTTP-слоя ``aiohttp``."""
    with aioresponses() as mocked:
        yield mocked


def url_for(path: str) -> re.Pattern[str]:
    """Паттерн URL метода API (query-параметры игнорируются)."""
    return re.compile(re.escape(BASE_URL + path) + r"(\?.*)?$")


def query_of(mocked: aioresponses, path: str, index: int = 0) -> dict[str, list[str]]:
    """Query-параметры ``index``-го запроса к указанному пути."""
    query = urlparse(str(request_url(mocked, path, index))).query
    return parse_qs(query, keep_blank_values=True)


def single_query(mocked: aioresponses, path: str, index: int = 0) -> dict[str, str]:
    """Query-параметры, где повторов не ожидается."""
    return {k: v[0] for k, v in query_of(mocked, path, index).items()}


def requests_to(mocked: aioresponses, path: str) -> list[Any]:
    """Все перехваченные запросы к указанному пути."""
    result: list[Any] = []
    for (_method, url), calls in mocked.requests.items():
        if urlparse(str(url)).path == path:
            result.extend(calls)
    return result


def request_url(mocked: aioresponses, path: str, index: int = 0) -> str:
    """URL ``index``-го запроса к указанному пути."""
    urls = [
        url
        for (_method, url), calls in mocked.requests.items()
        if urlparse(str(url)).path == path
        for _ in calls
    ]
    return str(urls[index])


def request_method(mocked: aioresponses, path: str) -> str:
    """HTTP-метод запроса к указанному пути."""
    for (method, url), _calls in mocked.requests.items():
        if urlparse(str(url)).path == path:
            return method
    msg = f"Не было запросов к {path}"
    raise AssertionError(msg)
