"""Обращение к боту по упоминанию.

Команда — барьер: в живом чате боту пишут как человеку, через `@`. Чтобы
это работало, надо надёжно понять, что упомянули именно нас.

Три способа опознания, от точного к запасным:

1. **Часть `parts` типа `mention`** — там лежит готовый `userId`, и это
   единственный источник, где он есть: разметка `format.mention` несёт
   только смещение и длину. Способ точный и не зависит ни от текста, ни
   от имени.
2. **Разметка `format.mention`** — по ней известно, какой кусок текста
   является упоминанием; остаётся посмотреть, не про нас ли он. Нужна,
   если `parts` почему-то не пришли.
3. **Текст напрямую** — `@[user_id]` или `@nick`. Нужен, когда человек
   напечатал ник руками, не выбирая из списка: части в этом случае нет.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

#: Упоминание по идентификатору — так его подставляет клиент VK Teams.
BRACKETS = "@[{user_id}]"

#: Отрезок текста: смещение и длина, как в ``format``.
type Span = tuple[int, int]


def by_id(user_id: str) -> str:
    """Упоминание по идентификатору."""
    return BRACKETS.format(user_id=user_id)


def spans_of(message_format: dict[str, Sequence[object]] | None) -> list[Span]:
    """Отрезки-упоминания из разметки сообщения.

    Разметка приходит словарём «тип → список отрезков»; нас интересует
    только ``mention``.
    """
    parts = (message_format or {}).get("mention") or []
    found: list[Span] = []
    for part in parts:
        offset = getattr(part, "offset", None)
        length = getattr(part, "length", None)
        if isinstance(offset, int) and isinstance(length, int) and length > 0:
            found.append((offset, length))
    return found


def _nick_pattern(nick: str) -> re.Pattern[str]:
    """`@nick` как отдельное слово.

    Граница справа обязательна: без неё `@bot` совпал бы внутри `@bot2`,
    и бот отвечал бы вместо соседа.
    """
    return re.compile(rf"@{re.escape(nick)}(?![\w])", re.IGNORECASE)


def _names(user_id: str | None, nick: str | None, first_name: str | None) -> list[str]:
    """По чему опознаём себя внутри отрезка-упоминания."""
    return [value for value in (user_id, nick, first_name) if value]


def _whole_word(value: str) -> re.Pattern[str]:
    """Имя целиком, а не как часть чужого.

    Подстроки мало: у бота имя вроде «Бот», и упоминание участника
    «Боталов» совпало бы с ним — бот отвечал бы на чужие обращения.
    Границы через lookaround, а не ``\b``: с кириллицей он ведёт себя
    предсказуемее.
    """
    return re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)


def matching_spans(
    text: str,
    spans: Iterable[Span],
    *,
    user_id: str | None,
    nick: str | None = None,
    first_name: str | None = None,
) -> list[Span]:
    """Отрезки разметки, в которых упомянут именно бот."""
    patterns = [_whole_word(name) for name in _names(user_id, nick, first_name)]
    if not patterns:
        return []
    matched: list[Span] = []
    for offset, length in spans:
        chunk = text[offset : offset + length]
        if any(pattern.search(chunk) for pattern in patterns):
            matched.append((offset, length))
    return matched


def mentions_bot(
    text: str,
    *,
    user_id: str | None,
    nick: str | None = None,
    first_name: str | None = None,
    spans: Iterable[Span] = (),
    mentioned_ids: Iterable[str] = (),
) -> bool:
    """Упомянут ли бот в сообщении.

    ``mentioned_ids`` — идентификаторы из частей сообщения. Проверяются
    первыми: это точное совпадение, остальное — восстановление по тексту.
    """
    if user_id and user_id in set(mentioned_ids):
        return True
    if not text:
        return False
    if matching_spans(text, spans, user_id=user_id, nick=nick, first_name=first_name):
        return True
    if user_id and by_id(user_id).lower() in text.lower():
        return True
    return bool(nick and _nick_pattern(nick).search(text))


def strip_mention(
    text: str,
    *,
    user_id: str | None,
    nick: str | None = None,
    first_name: str | None = None,
    spans: Iterable[Span] = (),
    mentioned_ids: Iterable[str] = (),  # noqa: ARG001
) -> str:
    """Убрать обращение к боту, оставив сам вопрос.

    Иначе модель получает вопрос с болтающимся `@[1011835311]` — и честно
    пытается понять, что это значит.

    Отрезки вырезаются с конца: иначе первое же удаление сдвинуло бы
    смещения остальных.

    ``mentioned_ids`` принимается для симметрии с ``mentions_bot``, но не
    используется: вырезать надо из текста, а часть сообщения говорит лишь
    о факте упоминания.
    """
    result = text
    matched = matching_spans(
        text, spans, user_id=user_id, nick=nick, first_name=first_name
    )
    for offset, length in sorted(matched, reverse=True):
        result = result[:offset] + " " + result[offset + length :]

    if user_id:
        result = re.sub(re.escape(by_id(user_id)), " ", result, flags=re.IGNORECASE)
    if nick:
        result = _nick_pattern(nick).sub(" ", result)

    # Обращение обычно стоит первым, и после него остаётся запятая или
    # двоеточие: «@бот, кто дежурный?».
    result = result.strip().lstrip(",:;-—–").strip()
    return re.sub(r"\s{2,}", " ", result)
