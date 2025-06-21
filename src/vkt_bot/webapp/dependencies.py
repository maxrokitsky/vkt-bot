from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from vkt_bot.core.models.user import User
from vkt_bot.core.repositories.user import UserRepository
from vkt_bot.webapp.db import DB
from vkt_bot.webapp.schemas.auth import TokenPayload
from vkt_bot.teams_bot.config import settings

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="login/access-token")


TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: DB, token: TokenDep) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        token_data = TokenPayload(**payload)
    except (jwt.InvalidTokenError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    user = await UserRepository(session).get(token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
