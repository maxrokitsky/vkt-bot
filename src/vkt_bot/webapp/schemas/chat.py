from pydantic import BaseModel, ConfigDict


class ChatResponse(BaseModel):
    id: str
    title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedChatsResponse(BaseModel):
    items: list[ChatResponse]
    total: int
    page: int
    size: int
    pages: int
