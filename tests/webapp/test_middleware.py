"""``RequestContextMiddleware``: идентификатор запроса и строка про ответ."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import auth_headers

if TYPE_CHECKING:
    import httpx

    from vkt_bot.core.models import ChatUser


class TestRequestId:
    """``X-Request-Id``."""

    async def test_response_carries_generated_id(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/health")

        assert response.headers["x-request-id"]

    async def test_incoming_id_is_reused(self, client: httpx.AsyncClient) -> None:
        """Идентификатор от балансировщика важнее своего: цепочка одна."""
        response = await client.get("/health", headers={"X-Request-Id": "outer-1"})

        assert response.headers["x-request-id"] == "outer-1"

    async def test_every_request_gets_its_own_id(
        self, client: httpx.AsyncClient
    ) -> None:
        first = await client.get("/health")
        second = await client.get("/health")

        assert first.headers["x-request-id"] != second.headers["x-request-id"]


class TestRequestLog:
    """Строка ``http.request``."""

    async def test_status_and_context(
        self, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot.webapp.http"):
            await client.get("/health", headers={"X-Request-Id": "req-1"})

        (record,) = [r for r in caplog.records if r.name == "vkt_bot.webapp.http"]
        message = record.getMessage()
        assert "http.request" in message
        assert "status=200" in message
        assert "req-1" in message
        assert "/health" in message
        assert "duration_ms" in message

    async def test_failed_request_is_logged_too(
        self, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ответ без авторизации тоже попадает в лог."""
        with caplog.at_level("INFO", logger="vkt_bot.webapp.http"):
            await client.get("/api/events")

        (record,) = [r for r in caplog.records if r.name == "vkt_bot.webapp.http"]
        assert "status=403" in record.getMessage()

    async def test_authenticated_request_knows_the_user(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``user_id`` привязывается зависимостью и доживает до строки ответа."""
        with caplog.at_level("INFO", logger="vkt_bot.webapp.http"):
            await client.get("/api/events", headers=auth_headers(superuser.id))

        (record,) = [r for r in caplog.records if r.name == "vkt_bot.webapp.http"]
        assert superuser.id in record.getMessage()
