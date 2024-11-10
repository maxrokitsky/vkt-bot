import logging.config
from typing import Any

from pydantic_core import MultiHostHost

from .config import settings
from pydantic.networks import MultiHostUrl


def mask_string(url: str) -> str:
    return '*' * len(url)


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
            masked_host["password"] = '*' * len(password)
        if port := host.get("port"):
            masked_host["port"] = port
        if _host := host.get("host"):
            masked_host["host"] = _host
        masked_hosts.append(masked_host)

    return str(
        MultiHostUrl.build(
            scheme=initial.scheme,
            fragment=initial.fragment,
            path=initial.path[1:] if initial.path else '',
            hosts=masked_hosts,
        )
    )


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(levelname)s %(asctime)s]: %(filename)s:%(lineno)s %(message)s',
        },
        'verbose': {
            'class': 'teams_bot.utils.ColorFormatter',
            # 'format': '[%(levelname)s %(asctime)s]: %(pathname)s:%(lineno)s::%(funcName)s\n %(message)s\n',
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['stdout'],
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        }
    },
    'loggers': {
        'teams_bot': {'level': settings.logging},
        'aio_pika': {'level': settings.rabbitmq_logging},
    }
}


def init_logging() -> None:
    logging.config.dictConfig(LOGGING)
    logger = logging.getLogger('teams_bot.settings')
    mask_settings = {
        'bot_token': mask_string,
        'db_url': mask_url,
        'broker_url': mask_url,
    }

    def format_setting(k: str, v: Any):
        if k in mask_settings:
            v = mask_settings[k](v)
        return f'{k}: {v}'

    msg = [f'   * {format_setting(k, v)}' for k, v in settings.model_dump().items()]
    logger.info('settings: \n%s\n', '\n'.join(msg))
