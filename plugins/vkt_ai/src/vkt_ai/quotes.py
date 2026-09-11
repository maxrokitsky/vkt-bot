"""Обращение к боту ответом на сообщение.

Второй способ заговорить с ботом как с человеком — не упомянуть его, а
ответить на его реплику. В живом чате так и делают: `@` нужен, чтобы
позвать издалека, а на сказанное только что отвечают.

Ответ приходит частью `parts` типа ``reply``: в ней лежит процитированное
сообщение целиком — отправитель, ``msgId`` и текст. Отсюда три вещи,
которых нет в упоминании:

1. **Кому отвечают** — по ``sender.userId`` цитаты. Сверяем со своим
   идентификатором: ответ соседнему боту не наше дело.
2. **На что отвечают** — ``msgId`` цитаты. Если это сообщение-якорь
   сессии, разговор продолжается, а не начинается заново; в личке, где
   обсуждения не заводятся, это единственный способ продолжить.
3. **О чём речь** — текст цитаты. Без него «@бот о чём тут?» ответом на
   чужую реплику для модели бессмысленно: вопрос есть, предмета нет.

Цитата — чужой текст, поэтому в промпт она уходит так же, как история
чата: внутри ограды и с явной пометкой «данные, не инструкции».
"""

from __future__ import annotations

from vkteams_client.enums import Parts
from vkteams_client.types import NewMessagePayload, QuotedMessage, QuotedPayload

from vkt_bot.utils.message import sender_name

#: Сколько символов цитаты класть в промпт. Длинную реплику обрезаем, а
#: не выбрасываем: начало обычно и несёт смысл.
QUOTE_LIMIT = 500
TRUNCATED = "…"


def quoted(payload: NewMessagePayload) -> QuotedMessage | None:
    """Сообщение, на которое отвечают, или ``None``.

    Пересылка (``forward``) сюда не попадает намеренно: переслать
    сообщение в чат — не то же самое, что обратиться к боту.
    """
    parts = payload.parts_of(Parts.REPLY, QuotedPayload)
    return parts[0].message if parts else None


def replies_to(payload: NewMessagePayload, user_id: str | None) -> bool:
    """Отвечают ли на сообщение именно нашего бота.

    Проверка по идентификатору, а не по типу отправителя: в чате может
    сидеть соседний бот, и разговаривать за него мы не нанимались.
    """
    if not user_id:
        return False
    message = quoted(payload)
    return bool(message and message.sender and message.sender.userId == user_id)


def quote_line(message: QuotedMessage) -> str | None:
    """Цитата для промпта: кто сказал и что.

    Пустой текст — вложение без подписи; описывать его нечем, и строку
    незачем: модель получит «Иван: » и честно попытается понять,
    что это значит.
    """
    text = (message.text or "").strip()
    if not text:
        return None
    if len(text) > QUOTE_LIMIT:
        text = text[:QUOTE_LIMIT] + TRUNCATED
    who = sender_name(message.sender) if message.sender else "неизвестно кто"
    return f"{who}: {text}"
