from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str
    is_superuser: bool = False
    is_active: bool = True


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    username: str
    email: str
    is_superuser: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PaginatedUsersResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    size: int
    pages: int
