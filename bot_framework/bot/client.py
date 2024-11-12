import logging
from typing import Any, Literal

import aiohttp

from .types import EventsResponse, GetMembersResponse, GetSelfResponse, Response

logger = logging.getLogger('teams_bot.client')


async def log_response(response: aiohttp.ClientResponse) -> dict[str, Any]:
    return {
        'ok': response.ok,
        'path': response.url.path,
        'status': response.status,
        'body': await response.json(),
        'method': response.method,
    }


class VkTeamsBot:
    """VkTeamsClient."""

    token: str
    _session: aiohttp.ClientSession | None = None
    base_url: str = 'https://myteam.mail.ru/bot/v1'

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
        path = '/self/get'

        async with self.session.get(
            url=self.base_url + path,
            params={'token': self.token},
        ) as response:
            response_body = await response.text()
            result = GetSelfResponse.model_validate_json(response_body)
            logger.debug(
                'VKTeamsBotApiResponse',
                extra=await log_response(response),
            )
            return result

    async def send_text(
        self,
        chat_id: str,
        text: str,
        forward_msg_id: str | None = None,
        forward_chat_id: str | None = None,
        parse_mode: Literal['MarkdownV2', 'HTML'] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> None:
        """Отправить текстовое сообщение."""
        path = '/messages/sendText'

        params: dict[str, str] = {
            'token': self.token,
            'chatId': chat_id,
            'text': text,
        }
        if forward_msg_id and forward_chat_id:
            params['forwardChatId'] = forward_chat_id
            params['forwardMsgId'] = forward_msg_id
        if parse_mode:
            params['parseMode'] = parse_mode
        if inline_keyboard_markup:
            params['inlineKeyboardMarkup'] = inline_keyboard_markup

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            logger.debug(
                'VKTeamsBotApiResponse',
                extra=await log_response(response),
            )

    async def edit_text(
        self,
        chat_id: str,
        msg_id: str,
        text: str,
        parse_mode: Literal['MarkdownV2', 'HTML'] | None = None,
        inline_keyboard_markup: Any = None,
    ) -> None:
        """Отправить текстовое сообщение."""
        path = '/messages/editText'

        params: dict[str, str] = {
            'token': self.token,
            'chatId': chat_id,
            'msgId': msg_id,
            'text': text,
        }
        if parse_mode:
            params['parseMode'] = parse_mode
        if inline_keyboard_markup:
            params['inlineKeyboardMarkup'] = inline_keyboard_markup

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            logger.debug(
                'VKTeamsBotApiResponse',
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
        path = '/messages/answerCallbackQuery'

        params: dict[str, str | bool] = {
            'token': self.token,
            'queryId': query_id,
        }
        if text is not None:
            params['text'] = text
        if show_alert:
            params['showAlert'] = 'true'
        if url:
            params['url'] = url

        async with self.session.get(
            url=self.base_url + path,
            params=params,
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            logger.debug(
                'VKTeamsBotApiResponse',
                extra=await log_response(response),
            )

    async def get_events(self, last_event_id: int, poll_time: int) -> EventsResponse:
        """Отправить текстовое сообщение."""
        path = '/events/get'

        async with self.session.get(
            url=self.base_url + path,
            params={
                'token': self.token,
                'lastEventId': last_event_id,
                'pollTime': poll_time,
            },
            timeout=aiohttp.ClientTimeout(30),
        ) as response:
            response_body = await response.text()
            result = EventsResponse.model_validate_json(response_body)
            if result.events:
                logger.debug(
                    'VKTeamsBotApiResponse',
                    extra=await log_response(response),
                )
            return result

    async def get_members(self, chat_id: str) -> GetMembersResponse:
        """Получить информацию о боте."""
        path = '/chats/getMembers'

        params = {'token': self.token, 'chatId': chat_id}
        async with self.session.get(
            url=self.base_url + path,
            params=params,
        ) as response:
            response_body = await response.text()
            result = GetMembersResponse.model_validate_json(response_body)
            logger.debug(
                'VKTeamsBotApiResponse',
                extra=await log_response(response),
            )
            return result

    async def delete_messages(self, chat_id: str, msg_id: str) -> Response:
        """Получить информацию о боте."""
        path = '/messages/deleteMessages'

        params = {'token': self.token, 'chatId': chat_id, 'msgId': msg_id}
        async with self.session.get(
            url=self.base_url + path,
            params=params,
        ) as response:
            response_body = await response.text()
            result = Response.model_validate_json(response_body)
            logger.debug(
                'VKTeamsBotApiResponse',
                extra=await log_response(response),
            )
            return result
