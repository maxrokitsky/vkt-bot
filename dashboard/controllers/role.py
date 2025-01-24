import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from bot_framework.exceptions import NotFoundError
from core.repositories.role import CreateRoleSchema, RoleRepository
from dashboard.db import DB
from dashboard.schemas.pagination import PaginatedResponse
from dashboard.schemas.role import CreateRoleAPISchema, DetailRoleAPISchema

roles_router = APIRouter(
    prefix="/roles",
    tags=["roles"],
)


@roles_router.get('', response_model=PaginatedResponse[DetailRoleAPISchema])
async def list_roles(session: DB, page: int = 1, page_size: int = 50) -> Any:
    query = RoleRepository(session).query()
    return await query.paginate(page=page, size=page_size)


@roles_router.get('/{role_id}', response_model=DetailRoleAPISchema)
async def get_role(session: DB, role_id: uuid.UUID) -> Any:
    role_repository = RoleRepository(session)
    try:
        return await role_repository.get(role_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Роль не найдена") from err

@roles_router.post('', response_model=DetailRoleAPISchema)
async def create_role(session: DB, role_data: CreateRoleAPISchema) -> Any:
    role_repository = RoleRepository(session)
    if await role_repository.get_by_name(role_data.name):
        raise HTTPException(status_code=404, detail="Роль уже существует")
    return await role_repository.create(CreateRoleSchema(name=role_data.name), commit=True)

