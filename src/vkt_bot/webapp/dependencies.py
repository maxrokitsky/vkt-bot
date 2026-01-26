from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.config import settings
from vkt_bot.core.models import ChatUser
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.db.session import async_session

security = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatUser:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_repo = ChatUserRepository(session)
    user = await user_repo.get_or_none(user_id)
    if user is None:
        raise credentials_exception

    return user


def is_owner(user: ChatUser) -> bool:
    """Check if user is the owner."""
    return settings.owner_id is not None and user.id == settings.owner_id


def is_admin(user: ChatUser) -> bool:
    """Check if user has admin privileges (owner or superuser)."""
    return user.is_superuser or is_owner(user)


async def get_current_admin_user(
    current_user: Annotated[ChatUser, Depends(get_current_user)],
) -> ChatUser:
    """Require current user to be admin (superuser or owner)."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required.",
        )
    return current_user


async def get_current_owner_user(
    current_user: Annotated[ChatUser, Depends(get_current_user)],
) -> ChatUser:
    """Require current user to be the owner."""
    if not is_owner(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Owner access required.",
        )
    return current_user


CurrentUser = Annotated[ChatUser, Depends(get_current_user)]
CurrentAdminUser = Annotated[ChatUser, Depends(get_current_admin_user)]
CurrentOwnerUser = Annotated[ChatUser, Depends(get_current_owner_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
