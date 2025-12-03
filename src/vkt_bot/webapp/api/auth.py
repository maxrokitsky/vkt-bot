from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from jose import jwt

from vkt_bot.config import settings
from vkt_bot.core.repositories.user import UserRepository
from vkt_bot.core.security import verify_password
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep
from vkt_bot.webapp.schemas.auth import LoginRequest, Token
from vkt_bot.webapp.schemas.user import UserResponse

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
async def login(login_data: LoginRequest, session: SessionDep) -> Token:
    """Login and get JWT token."""
    user_repo = UserRepository(session)

    # Find user by username
    user = await user_repo.get_by_username(login_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create access token
    access_token = create_access_token(data={"sub": user.username})

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)
