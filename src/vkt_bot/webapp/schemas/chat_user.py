from uuid import UUID

from pydantic import BaseModel, ConfigDict

from vkteams_client.enums import ChatType
from vkt_bot.webapp.schemas.user import ChatUserFields


class ChatUserRoleResponse(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class ChatUserChatResponse(BaseModel):
    id: str
    type: ChatType
    title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ChatUserResponse(ChatUserFields):
    """Участник в списке — со ролями, чтобы список отвечал на «у кого что»."""

    roles: list[ChatUserRoleResponse]


class ChatUserDetailResponse(ChatUserResponse):
    chats: list[ChatUserChatResponse]


class PaginatedChatUsersResponse(BaseModel):
    items: list[ChatUserResponse]
    total: int
    page: int
    size: int
    pages: int


class AssignRoleRequest(BaseModel):
    role_id: str


class RemoveRoleRequest(BaseModel):
    role_id: str


class UpdateChatUserRequest(BaseModel):
    is_superuser: bool
