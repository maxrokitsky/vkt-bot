from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация."""

    logging: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']# = 'INFO'
    rabbitmq_logging: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    bot_token: str
    db_url: PostgresDsn
    broker_url: str
    owner_id: str | None = None
    log_file: Path | None = None

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', case_sensitive=False, extra="ignore"
    )


settings = Settings()  # type: ignore [reportCallIssue]
print('logging', settings.logging)
