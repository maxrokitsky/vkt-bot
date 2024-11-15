import logging.config
from copy import deepcopy
from typing import Any

from pydantic_core import MultiHostHost, MultiHostUrl

from .config import settings


def mask_string(url: str) -> str:
    return '*' * len(url)


def mask_url(url: str | MultiHostUrl) -> str:
    initial = MultiHostUrl(url) if isinstance(url, str) else url
    hosts = initial.hosts()
    masked_hosts: list[MultiHostHost] = []
    for host in hosts:
        masked_host: MultiHostHost = {
            'username': '',
            'password': '',
            'port': None,
            'host': '',
        }
        if username := host.get('username'):
            masked_host['username'] = username
        if password := host.get('password'):
            masked_host['password'] = '*' * len(password)
        if port := host.get('port'):
            masked_host['port'] = port
        if _host := host.get('host'):
            masked_host['host'] = _host
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
        # 'verbose': {
        #     'class': 'teams_bot.utils.ColorFormatter',
        #     # 'format': '[%(levelname)s %(asctime)s]: %(pathname)s:%(lineno)s::%(funcName)s\n %(message)s\n',
        # },
        'json': {
            '()': 'teams_bot.utils.JsonFormatter',
            'fmt_keys': {
                'level': 'levelname',
                'message': 'message',
                'timestamp': 'timestamp',
                'logger': 'name',
                'module': 'module',
                'function': 'funcName',
                'line': 'lineno',
                'thread_name': 'threadName',
            },
        },
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['stderr'],
    },
    'handlers': {
        'stderr': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stderr',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'json',
            'filename': settings.log_file or '/dev/null',
            'maxBytes': 1000000,
            'backupCount': 3,
        },
    },
    'loggers': {
        'teams_bot': {'level': settings.logging},
        'aio_pika': {'level': settings.rabbitmq_logging},
    },
}


def init_logging() -> None:
    logging_config = deepcopy(LOGGING)
    if settings.log_file:
        if not settings.log_file.parent.exists():
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        logging_config['root']['handlers'].append('file')

    logging.config.dictConfig(logging_config)
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
