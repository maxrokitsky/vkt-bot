import logging.config
from pathlib import Path
from typing import Any

from pydantic_core import MultiHostHost, MultiHostUrl
import yaml

from vkt_bot.teams_bot.config import settings


def mask_string(url: str) -> str:
    return "*" * len(url)


def mask_url(url: str | MultiHostUrl) -> str:
    initial = MultiHostUrl(url) if isinstance(url, str) else url
    hosts = initial.hosts()
    masked_hosts: list[MultiHostHost] = []
    for host in hosts:
        masked_host: MultiHostHost = {
            "username": "",
            "password": "",
            "port": None,
            "host": "",
        }
        if username := host.get("username"):
            masked_host["username"] = username
        if password := host.get("password"):
            masked_host["password"] = "*" * len(password)
        if port := host.get("port"):
            masked_host["port"] = port
        if _host := host.get("host"):
            masked_host["host"] = _host
        masked_hosts.append(masked_host)

    return str(
        MultiHostUrl.build(
            scheme=initial.scheme,
            fragment=initial.fragment,
            path=initial.path[1:] if initial.path else "",
            hosts=masked_hosts,
        )
    )


def import_logging():
    config_path = Path(__file__).parent / "logging.yaml"
    with config_path.open() as f:
        config = yaml.safe_load(f)
    return config


def init_logging() -> None:
    logging_config = import_logging()
    if settings.log_file:
        if not settings.log_file.parent.exists():
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        logging_config["handlers"]["file"]["filename"] = settings.log_file.absolute()
        logging_config["root"]["handlers"].append("file")

    logging.config.dictConfig(logging_config)
    logger = logging.getLogger("teams_bot.settings")
    mask_settings = {
        "bot_token": mask_string,
        "db_url": mask_url,
        "broker_url": mask_url,
        "secret_key": mask_string,
        "sentry_dsn": mask_string,
    }

    def format_setting(k: str, v: Any):
        if k in mask_settings:
            v = mask_settings[k](v) if v else "<NOT_SET>"
        return f"{k}: {v}"

    msg = [f"   * {format_setting(k, v)}" for k, v in settings.model_dump().items()]
    logger.info("settings: \n%s\n", "\n".join(msg))

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(settings.sentry_dsn)
