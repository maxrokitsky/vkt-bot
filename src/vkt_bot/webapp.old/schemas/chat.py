from pydantic import BaseModel

from vkteams_client.enums import ChatType


class DetailChatAPIModel(BaseModel):
    id: str
    type: ChatType
