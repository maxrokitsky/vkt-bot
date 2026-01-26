from pydantic import BaseModel, ConfigDict, computed_field

from vkt_bot.config import settings


class ChatUserResponse(BaseModel):
    id: str
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_owner(self) -> bool:
        """Check if this user is the owner."""
        return settings.owner_id is not None and self.id == settings.owner_id


class ChatUserRoleResponse(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class ChatUserChatResponse(BaseModel):
    id: str
    type: str

    model_config = ConfigDict(from_attributes=True)


class ChatUserDetailResponse(ChatUserResponse):
    roles: list[ChatUserRoleResponse]
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
