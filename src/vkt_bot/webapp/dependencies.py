from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.config import settings
from vkt_bot.core.models.user import User
from vkt_bot.core.repositories.user import UserRepository
from vkt_bot.db.session import async_session

security = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.secret_key, algorithms=["HS256"]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_repo = UserRepository(session)
    user = await user_repo.get_or_none(user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require current user to be admin."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required.",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
