"""Middleware веб-приложения: контекст логирования на каждый запрос."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
import uuid

import structlog

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger("vkt_bot.webapp.http")

REQUEST_ID_HEADER = b"x-request-id"


class RequestContextMiddleware:
    """Привязать к запросу ``request_id`` и записать строку про ответ.

    Чистый ASGI, а не ``BaseHTTPMiddleware``: последний выполняет
    приложение в отдельной задаче anyio, и правила видимости contextvars
    там неочевидны — здесь же контекст ставится ровно в той задаче, где
    работает обработчик.

    ``request_id`` берётся из одноимённого заголовка, если он пришёл от
    балансировщика, иначе генерируется: так одна цепочка запросов видна
    целиком.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(REQUEST_ID_HEADER)
        request_id = incoming.decode("latin-1") if incoming else uuid.uuid4().hex

        # Чужие поля из предыдущего запроса на этом же соединении не нужны:
        # задача своя, но контекст мог остаться от keep-alive.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=scope.get("method"),
            path=scope.get("path"),
        )

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (REQUEST_ID_HEADER, request_id.encode("latin-1")),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            # Своя строка вместо access-лога uvicorn: тот пишет мимо
            # структурного формата и не знает про request_id.
            logger.info(
                "http.request",
                status=status_code,
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()
