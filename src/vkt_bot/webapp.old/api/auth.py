import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from vkt_bot.core.repositories.user import UserRepository
from vkt_bot.core.security import create_access_token
from vkt_bot.webapp.db import DB
from vkt_bot.webapp.schemas.auth import Token
from vkt_bot.config import settings

auth_router = APIRouter(tags=["login"])


@auth_router.post("/login/access-token")
async def login_access_token(
    session: DB, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Получить Access Token."""
    user = await UserRepository(session).authenticate(
        email_or_username=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    # if not user.is_active:
    # raise HTTPException(status_code=400, detail='Inactive user')
    access_token_expires = datetime.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return Token(
        access_token=create_access_token(
            user.username, expires_delta=access_token_expires
        )
    )
