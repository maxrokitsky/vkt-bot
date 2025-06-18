from datetime import UTC, datetime, timedelta
import random
import string
from typing import Any

import jwt
from passlib.context import CryptContext

from teams_bot.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_random_string(length: int = 32) -> str:
    allowed_chars = ''.join((string.ascii_letters, string.digits))
    return ''.join(random.choice(allowed_chars) for _ in range(length))
    