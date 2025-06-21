from pydantic import BaseModel

from vkt_bot.bot_framework.bot.enums import ChatType


class DetailChatAPIModel(BaseModel):
    id: str
    type: ChatType
