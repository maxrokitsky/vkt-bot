from pathlib import Path
import sys
from typing import Literal

from pydantic import PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class VktSettings(BaseSettings):
    """Конфигурация."""

    logging: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]  # = 'INFO'
    rabbitmq_logging: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    bot_token: str
    db_url: PostgresDsn
    owner_id: str | None = None
    log_file: Path | None = None
    secret_key: str  # Required for JWT authentication
    public_url: str | None = None
    sentry_dsn: str | None = None
    access_token_expire_minutes: int = 60 * 24 * 8

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


try:
    settings = VktSettings()
except ValidationError as e:
    print(e, file=sys.stderr)
    sys.exit(1)
