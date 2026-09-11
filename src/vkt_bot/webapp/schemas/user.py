from pydantic import BaseModel, ConfigDict, computed_field

from vkt_bot.core.security import is_owner


class ChatUserFields(BaseModel):
    """Поля модели ``ChatUser``, общие для всех ответов о пользователе.

    ``display_name`` собирается здесь, а не на фронте: правило «имя, иначе
    ник, иначе id» должно быть одним на всю систему.
    """

    id: str
    is_superuser: bool
    is_bot: bool
    first_name: str | None = None
    last_name: str | None = None
    nick: str | None = None
    about: str | None
    #: Ссылка на аватар из ``chats/getInfo``: открывается без
    #: авторизации, поэтому отдаём её как есть. Картинки за ссылкой
    #: может и не быть — фронт обязан иметь фолбэк на инициалы.
    photo_url: str | None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_owner(self) -> bool:
        """Пользователь — владелец бота (``OWNER_ID``)."""
        return is_owner(self.id)

    @computed_field
    @property
    def display_name(self) -> str:
        """Имя для показа. Пока имя неизвестно — остаётся ``id``."""
        full_name = " ".join(filter(None, (self.first_name, self.last_name)))
        return full_name or self.nick or self.id


class UserResponse(ChatUserFields):
    """Текущий пользователь панели."""
