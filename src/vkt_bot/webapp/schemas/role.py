from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoleBase(BaseModel):
    name: str


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = None


class RoleResponse(RoleBase):
    id: UUID
    member_count: int

    model_config = ConfigDict(from_attributes=True)


class RoleMemberResponse(BaseModel):
    user_id: str
    display_name: str
    is_bot: bool

    model_config = ConfigDict(from_attributes=True)


class RoleWithMembersResponse(RoleResponse):
    members: list[RoleMemberResponse]


class AddRoleMemberRequest(BaseModel):
    user_id: str


class PaginatedRolesResponse(BaseModel):
    items: list[RoleResponse]
    total: int
    page: int
    size: int
    pages: int
