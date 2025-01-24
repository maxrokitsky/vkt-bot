from pydantic import BaseModel

from bot_framework.bot.enums import ChatType


class DetailChatAPIModel(BaseModel):
    id: str
    type: ChatType
