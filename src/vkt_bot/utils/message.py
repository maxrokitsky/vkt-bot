from vkteams_client.types import Bot, User


def mention(user_id: str) -> str:
    return f"@[{user_id}]"


def sender_name(sender: User | Bot) -> str:
    """Имя отправителя события.

    У ботов нет фамилии, зато есть ``nick``. Если не известно ничего —
    остаётся идентификатор.
    """
    first = sender.firstName or ""
    last = getattr(sender, "lastName", "") or ""
    full = " ".join(filter(None, (first, last)))
    return full or getattr(sender, "nick", "") or sender.userId
