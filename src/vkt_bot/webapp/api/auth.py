import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt

from vkt_bot.config import settings
from vkt_bot.core.repositories.login_history import LoginHistoryRepository
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep
from vkt_bot.webapp.schemas.auth import Token, TokenLoginRequest
from vkt_bot.webapp.schemas.user import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt


@router.post("/login", response_model=Token)
async def login(
    request: Request, login_data: TokenLoginRequest, session: SessionDep
) -> Token:
    """Login with temporary token from bot."""
    token_repo = LoginTokenRepository(session)
    history_repo = LoginHistoryRepository(session)

    token_value = login_data.token.strip()
    logger.debug("Login attempt with token: %s...", token_value[:10] if len(token_value) > 10 else token_value)

    login_token = await token_repo.get_by_token(token_value)
    if not login_token:
        logger.warning("Token not found in database: %s...", token_value[:10] if len(token_value) > 10 else token_value)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    # expires_at stored as naive UTC datetime in DB
    if login_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )

    if login_token.used:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token already used"
        )

    await token_repo.mark_used(login_token)

    ip_address = None
    if request.client:
        ip_address = request.client.host

    await history_repo.log_login(
        user_id=login_token.user_id,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()

    access_token = create_access_token(data={"sub": login_token.user_id})

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)
