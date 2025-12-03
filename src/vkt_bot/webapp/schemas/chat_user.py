from pydantic import BaseModel, ConfigDict


class ChatUserResponse(BaseModel):
    id: str

    model_config = ConfigDict(from_attributes=True)


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
