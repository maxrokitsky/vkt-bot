import json
import logging
from typing import Any, Literal

import aiohttp

from .types import (
    EventsResponse,
    GetMembersResponse,
    GetSelfResponse,
    MsgLoadFileResponse,
    MsgResponse,
    Response,
)
from .loggers import events_logger, send_message_logger

logger = logging.getLogger("teams_bot.client")


async def log_response(response: aiohttp.ClientResponse) -> dict[str, Any]:
    return {
        "ok": response.ok,
        "path": response.url.path,
        "status": response.status,
        "body": await response.json(),
        "method": response.method,
    }


class VKTeams:
    """VKTeams."""

    token: str
    _session: aiohttp.ClientSession | None = None
    base_url: str = "https://myteam.mail.ru/bot/v1"

    def __init__(self, token: str) -> None:
        self.token = token

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
            logger.debug(
                "Информация о боте",
                extra=await log_response(response),
            )
            return result

    async def send_text(
        self,
        chat_id: str,
        text: str,
        forward_msg_id: str | None = None,
        forward_chat_id: str | None = None,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> None:
        """Отправить текстовое сообщение."""
        path = "/messages/sendText"

        params: dict[str, str] = {
            "token": self.token,
            "chatId": chat_id,
            "text": text,
        }
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
            send_message_logger.info(
                "Сообщение отправлено (chatId: %s, text: %r)",
                chat_id,
                text[:50],
                extra=await log_response(response),
            )

    async def edit_text(
        self,
        chat_id: str,
        msg_id: str,
        text: str,
        parse_mode: Literal["MarkdownV2", "HTML"] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> None:
        """Отправить текстовое сообщение."""
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
            logger.debug(
                "Сообщение отредактировано",
                extra=await log_response(response),
            )

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
            logger.debug(
                "Ответ на callback",
                extra=await log_response(response),
            )

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
                    events_logger.info("Событие %s", event, extra=event.model_dump())
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
            logger.debug(
                "Список пользователей",
                extra=await log_response(response),
            )
            return result

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
            logger.debug(
                "Удаление сообщения",
                extra=await log_response(response),
            )
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
                    "Файл отправлен по file_id (chatId: %s, fileId: %s)",
                    chat_id,
                    file_id,
                    extra=await log_response(response),
                )
                return result
        elif file:
            # Загрузка и отправка нового файла (POST multipart/form-data)
            data = aiohttp.FormData()

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
                    "Файл загружен и отправлен (chatId: %s, filename: %s)",
                    chat_id,
                    filename or "unknown",
                    extra=await log_response(response),
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
