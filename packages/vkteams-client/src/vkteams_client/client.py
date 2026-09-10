import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

import aiohttp

from .types import (
    EventsResponse,
    GetMembersResponse,
    GetSelfResponse,
    MsgLoadFileResponse,
    MsgResponse,
    Response,
    Subscriber,
    ThreadAddResponse,
    ThreadSubscribersResponse,
)
from .loggers import events_logger, main_logger as logger, send_message_logger


class ThreadSubscribersError(RuntimeError):
    """Сервер отказал в выдаче подписчиков обсуждения."""


async def log_response(response: aiohttp.ClientResponse) -> dict[str, Any]:
    return {
        "ok": response.ok,
        "path": response.url.path,
        "status": response.status,
        "body": await response.json(),
        "method": response.method,
    }


def _query_bool(value: bool) -> str:  # noqa: FBT001
    """Булев query-параметр: aiohttp сам `bool` в строку не превращает."""
    return "true" if value else "false"


class VKTeams:
    """VKTeams."""

    token: str
    _session: aiohttp.ClientSession | None = None
    base_url: str = "https://myteam.mail.ru/bot/v1"
    #: Куда сообщать о том, что бот сделал. Приложение подставляет сюда
    #: свою функцию и превращает вызовы в доменные события; пакет про них
    #: ничего не знает и в базу не ходит.
    event_sink: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None

    def __init__(self, token: str) -> None:
        self.token = token

    async def notify(self, event_type: str, **fields: Any) -> None:  # noqa: ANN401
        """Сообщить наблюдателю о действии бота.

        Ошибка наблюдателя не должна ломать отправку сообщения: журнал
        событий — не причина не доставить текст пользователю.
        """
        if self.event_sink is None:
            return
        try:
            await self.event_sink(event_type, fields)
        except Exception:
            logger.exception("event_sink.failed", event_type=event_type)

    @property
    def session(self) -> aiohttp.ClientSession:
        """Сессия."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрыть."""
        if self._session:
            await self._session.close()

    async def get_self(self) -> GetSelfResponse:
        """Получить информацию о боте."""
        path = "/self/get"

        async with self.session.get(
            url=self.base_url + path,
            params={"token": self.token},
        ) as response:
            response_body = await response.text()
            result = GetSelfResponse.model_validate_json(response_body)
            logger.debug("api.self", **await log_response(response))
            return result

    async def send_text(
        self,
        chat_id: str,
        text: str,
        reply_msg_id: list[int] | None = None,
        forward_msg_id: str | None = None,
        forward_chat_id: str | None = None,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> MsgResponse:
        """Отправить текстовое сообщение.

        Отдельного метода для обсуждений нет: у треда свой ``chatId``
        (``threads_add`` отдаёт его в ``threadId``), поэтому сообщение в
        тред — обычный ``sendText`` с ``chat_id=thread_id``.

        Отказ сервера (``ok: false``) исключением не является: он
        возвращается вызывающему и пишется в лог как ошибка.
        """
        path = "/messages/sendText"

        params: dict[str, str] = {
            "token": self.token,
            "chatId": chat_id,
            "text": text,
        }
        if reply_msg_id:
            params["replyMsgId"] = reply_msg_id
        if forward_msg_id and forward_chat_id:
            params["forwardChatId"] = forward_chat_id
            params["forwardMsgId"] = forward_msg_id
        if parse_mode:
            params["parseMode"] = parse_mode
        if inline_keyboard_markup:
            params["inlineKeyboardMarkup"] = inline_keyboard_markup

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = MsgResponse.model_validate_json(response_body)
            extra = await log_response(response)
            if result.ok:
                send_message_logger.info(
                    "message.sent",
                    chat_id=chat_id,
                    text_preview=text[:50],
                    **extra,
                )
            else:
                send_message_logger.error(
                    "message.send_failed",
                    chat_id=chat_id,
                    text_preview=text[:50],
                    reason=result.description,
                    **extra,
                )
            await self.notify(
                "message.sent" if result.ok else "message.send_failed",
                chat_id=chat_id,
                text_preview=text[:50],
                reason=result.description,
            )
            return result

    async def edit_text(
        self,
        chat_id: str,
        msg_id: str,
        text: str,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> MsgResponse:
        """Отредактировать сообщение."""
        path = "/messages/editText"

        params: dict[str, str] = {
            "token": self.token,
            "chatId": chat_id,
            "msgId": msg_id,
            "text": text,
        }
        if parse_mode:
            params["parseMode"] = parse_mode
        if inline_keyboard_markup:
            params["inlineKeyboardMarkup"] = inline_keyboard_markup

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = MsgResponse.model_validate_json(response_body)
            extra = await log_response(response)
            if result.ok:
                logger.debug("message.edited", chat_id=chat_id, **extra)
            else:
                logger.error(
                    "message.edit_failed",
                    chat_id=chat_id,
                    reason=result.description,
                    **extra,
                )
            return result

    async def answer_callback_query(
        self,
        query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
        url: str | None = None,
    ) -> None:
        """Отправить текстовое сообщение."""
        path = "/messages/answerCallbackQuery"

        params: dict[str, str | bool] = {
            "token": self.token,
            "queryId": query_id,
        }
        if text is not None:
            params["text"] = text
        if show_alert:
            params["showAlert"] = "true"
        if url:
            params["url"] = url

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            logger.debug("api.callback_answered", **await log_response(response))

    async def get_events(self, last_event_id: int, poll_time: int) -> EventsResponse:
        """Отправить текстовое сообщение."""
        path = "/events/get"

        async with self.session.get(
            url=self.base_url + path,
            params={
                "token": self.token,
                "lastEventId": last_event_id,
                "pollTime": poll_time,
            },
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = EventsResponse.model_validate_json(response_body)
            if result.events:
                for event in result.events:
                    events_logger.info(
                        "api.event_received",
                        event_id=event.eventId,
                        event_type=str(event.type),
                        payload=event.payload,
                    )
            return result

    async def get_members(self, chat_id: str) -> GetMembersResponse:
        """Получить информацию о боте."""
        path = "/chats/getMembers"

        params = {"token": self.token, "chatId": chat_id}
        async with self.session.get(
            url=self.base_url + path,
            params=params,
        ) as response:
            response_body = await response.text()
            result = GetMembersResponse.model_validate_json(response_body)
            logger.debug("api.members_fetched", **await log_response(response))
            return result

    async def threads_add(self, chat_id: str, msg_id: str) -> ThreadAddResponse:
        """Создать обсуждение (тред) к сообщению чата или получить существующее.

        Метод ведёт себя как get-or-create: повторный вызов на том же
        ``(chat_id, msg_id)`` не создаёт второй тред и не отдаёт ошибку —
        приходит тот же ``threadId`` (проверено на живом стенде
        2026-09-10). Другого способа узнать id уже существующего
        обсуждения в API нет: в событиях ссылки на тред не приходят, а
        методов вроде ``threads/get`` в спеке не существует. Обратная
        сторона — вызов не только читает: у сообщения без обсуждения он
        его создаст.

        Бот должен быть участником чата. Возвращённый ``threadId`` — это
        полноценный ``chatId``: в тред пишут обычным ``send_text``.
        Вложенных обсуждений нет — с ``chat_id`` треда метод отвечает
        ``Bad request``.
        """
        path = "/threads/add"

        params = {"token": self.token, "chatId": chat_id, "msgId": msg_id}
        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = ThreadAddResponse.model_validate_json(response_body)
            logger.debug("api.thread_added", **await log_response(response))
            return result

    async def threads_autosubscribe(
        self,
        chat_id: str,
        enable: bool,
        with_existing: bool | None = None,
    ) -> Response:
        """Управлять автоподпиской бота на обсуждения чата.

        При включённой автоподписке бот сам подписывается на новые треды и
        получает из них события. ``with_existing=True`` добавляет к ним уже
        существующие треды чата. Бот должен быть участником чата.
        """
        path = "/threads/autosubscribe"

        params = {
            "token": self.token,
            "chatId": chat_id,
            "enable": _query_bool(enable),
        }
        if with_existing is not None:
            params["withExisting"] = _query_bool(with_existing)

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = Response.model_validate_json(response_body)
            logger.debug("api.thread_autosubscribed", **await log_response(response))
            return result

    async def threads_subscribers_get(
        self,
        thread_id: str,
        page_size: int | None = None,
        cursor: str | None = None,
    ) -> ThreadSubscribersResponse:
        """Получить страницу подписчиков обсуждения.

        Хотя бы один из ``page_size`` и ``cursor`` обязателен: без них
        сервер отвечает ``Bad request``.

        Постраничный обход удобнее делать через ``iter_thread_subscribers``.
        """
        if page_size is None and cursor is None:
            msg = "Нужен page_size или cursor"
            raise ValueError(msg)

        path = "/threads/subscribers/get"

        params: dict[str, str | int] = {"token": self.token, "threadId": thread_id}
        if page_size is not None:
            params["pageSize"] = page_size
        if cursor is not None:
            params["cursor"] = cursor

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = ThreadSubscribersResponse.model_validate_json(response_body)
            logger.debug("api.thread_subscribers", **await log_response(response))
            return result

    async def iter_thread_subscribers(
        self,
        thread_id: str,
        page_size: int = 100,
    ) -> AsyncIterator[Subscriber]:
        """Все подписчики обсуждения с автопагинацией по ``cursor``."""
        cursor: str | None = None
        while True:
            page = await self.threads_subscribers_get(
                thread_id=thread_id,
                page_size=page_size,
                cursor=cursor,
            )
            if not page.ok:
                # Иначе отказ неотличим от обсуждения без подписчиков.
                msg = page.description or "Не удалось получить подписчиков"
                raise ThreadSubscribersError(msg)

            for subscriber in page.subscribers:
                yield subscriber
            # Страница без курсора или без подписчиков — конец списка.
            if not page.cursor or not page.subscribers:
                return
            cursor = page.cursor

    async def delete_messages(self, chat_id: str, msg_id: str) -> Response:
        """Получить информацию о боте."""
        path = "/messages/deleteMessages"

        params = {"token": self.token, "chatId": chat_id, "msgId": msg_id}
        async with self.session.get(
            url=self.base_url + path,
            params=params,
        ) as response:
            response_body = await response.text()
            result = Response.model_validate_json(response_body)
            logger.debug("api.messages_deleted", **await log_response(response))
            return result

    async def send_file(
        self,
        chat_id: str,
        file_id: str | None = None,
        *,
        file: bytes | None = None,
        filename: str | None = None,
        caption: str | None = None,
        reply_msg_id: list[int] | None = None,
        forward_chat_id: str | None = None,
        forward_msg_id: list[int] | None = None,
        inline_keyboard_markup: Any = None,
        format: dict[str, Any] | None = None,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
    ) -> MsgResponse | MsgLoadFileResponse:
        """Отправить файл.

        Использует file_id для отправки уже загруженного файла или
        загружает новый файл через multipart/form-data.

        Args:
            chat_id: ID чата для отправки файла
            file_id: ID уже загруженного файла (для GET запроса)
            file: Бинарные данные файла (для POST запроса)
            filename: Имя файла (только для POST запроса)
            caption: Подпись к файлу
            reply_msg_id: Список ID сообщений для ответа
            forward_chat_id: ID чата для пересылки
            forward_msg_id: Список ID сообщений для пересылки
            inline_keyboard_markup: Inline клавиатура в формате JSON
            format: Форматирование текста в формате JSON
            parse_mode: Режим парсинга текста (MarkdownV2 или HTML)

        Returns:
            MsgResponse: Для GET запроса (только msgId)
            MsgLoadFileResponse: Для POST запроса (fileId и msgId)

        Raises:
            ValueError: Если не указан ни file_id, ни file

        Examples:
            ```python
            # Отправка уже загруженного файла
            result = await client.send_file(
                chat_id="123456789@chat.agent",
                file_id="0dC76vcKS3XZOtG5DVs9y15d1daefa1ae",
                caption="Вот ваш файл!",
            )
            print(f"Сообщение отправлено: {result.msgId}")

            # Отправка нового файла
            with open("document.pdf", "rb") as f:
                file_content = f.read()

            result = await client.send_file(
                chat_id="123456789@chat.agent",
                file=file_content,
                filename="document.pdf",
                caption="Документ для вас",
            )
            print(f"Файл отправлен: {result.fileId}, сообщение: {result.msgId}")
            ```
        """
        path = "/messages/sendFile"

        # Базовые query параметры
        params: dict[str, str | list[int]] = {
            "token": self.token,
            "chatId": chat_id,
        }
        if caption:
            params["caption"] = caption
        if reply_msg_id:
            params["replyMsgId"] = reply_msg_id
        if forward_chat_id and forward_msg_id:
            params["forwardChatId"] = forward_chat_id
            params["forwardMsgId"] = forward_msg_id
        if parse_mode:
            params["parseMode"] = parse_mode

        if file_id:
            # Отправка уже загруженного файла по file_id (GET)
            params["fileId"] = file_id

            # Для GET запроса inlineKeyboardMarkup и format должны быть в query параметрах
            # как JSON строки
            if inline_keyboard_markup:
                params["inlineKeyboardMarkup"] = json.dumps(inline_keyboard_markup)
            if format:
                params["format"] = json.dumps(format)

            async with self.session.get(
                url=self.base_url + path,
                params=params,
                timeout=aiohttp.ClientTimeout(30),
            ) as response:
                response_body = await response.text()
                result = MsgResponse.model_validate_json(response_body)
                send_message_logger.info(
                    "file.sent",
                    chat_id=chat_id,
                    file_id=file_id,
                    **await log_response(response),
                )
                return result
        elif file:
            # Загрузка и отправка нового файла (POST multipart/form-data)
            data = aiohttp.FormData(quote_fields=False)

            # Добавляем query параметры
            for key, value in params.items():
                if isinstance(value, list):
                    # Преобразуем списки в JSON строки
                    data.add_field(key, json.dumps(value))
                else:
                    data.add_field(key, str(value))

            # Добавляем body параметры (inlineKeyboardMarkup и format)
            if inline_keyboard_markup:
                data.add_field(
                    "inlineKeyboardMarkup", json.dumps(inline_keyboard_markup)
                )
            if format:
                data.add_field("format", json.dumps(format))

            # Добавляем файл
            data.add_field("file", file, filename=filename or "file")

            async with self.session.post(
                url=self.base_url + path,
                data=data,
                timeout=aiohttp.ClientTimeout(60),  # Больше времени для загрузки файла
            ) as response:
                response_body = await response.text()
                result = MsgLoadFileResponse.model_validate_json(response_body)
                send_message_logger.info(
                    "file.uploaded",
                    chat_id=chat_id,
                    filename=filename or "unknown",
                    **await log_response(response),
                )
                return result
        else:
            raise ValueError("Необходимо указать либо file_id, либо file")

    async def send_file_from_url(
        self,
        chat_id: str,
        url: str,
        *,
        filename: str | None = None,
        caption: str | None = None,
        reply_msg_id: list[int] | None = None,
        forward_chat_id: str | None = None,
        forward_msg_id: list[int] | None = None,
        inline_keyboard_markup: Any = None,
        format: dict[str, Any] | None = None,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
    ) -> MsgLoadFileResponse:
        """Отправить файл по URL.

        Скачивает файл по URL и отправляет его через send_file.

        Args:
            chat_id: ID чата для отправки файла
            url: URL файла для скачивания
            filename: Имя файла (если не указано, будет извлечено из URL или заголовков)
            caption: Подпись к файлу
            reply_msg_id: Список ID сообщений для ответа
            forward_chat_id: ID чата для пересылки
            forward_msg_id: Список ID сообщений для пересылки
            inline_keyboard_markup: Inline клавиатура в формате JSON
            format: Форматирование текста в формате JSON
            parse_mode: Режим парсинга текста (MarkdownV2 или HTML)

        Returns:
            MsgLoadFileResponse: fileId и msgId отправленного файла

        Raises:
            ValueError: Если не удалось скачать файл по URL

        Examples:
            ```python
            result = await client.send_file_from_url(
                chat_id="123456789@chat.agent",
                url="https://example.com/document.pdf",
                caption="Файл из интернета",
            )
            print(f"Файл отправлен: {result.fileId}, сообщение: {result.msgId}")
            ```
        """
        # Скачиваем файл по URL
        async with self.session.get(url) as response:
            if not response.ok:
                raise ValueError(f"Не удалось скачать файл по URL: {url}")

            file_content = await response.read()
            if not filename:
                # Пытаемся извлечь имя файла из URL или заголовков
                content_disposition = response.headers.get("Content-Disposition", "")
                if "filename=" in content_disposition:
                    import re

                    match = re.search(r'filename="([^"]+)"', content_disposition)
                    if match:
                        filename = match.group(1)
                if not filename:
                    # Используем последнюю часть URL как имя файла
                    filename = url.split("/")[-1].split("?")[0] or "file"

            return await self.send_file(
                chat_id=chat_id,
                file=file_content,
                filename=filename,
                caption=caption,
                reply_msg_id=reply_msg_id,
                forward_chat_id=forward_chat_id,
                forward_msg_id=forward_msg_id,
                inline_keyboard_markup=inline_keyboard_markup,
                format=format,
                parse_mode=parse_mode,
            )
