"""Настройка логирования: structlog поверх стандартного ``logging``.

Один поток вывода (stdout) и один формат на процесс: ``console`` для
локальной отладки, ``json`` для Loki. Сторонние логгеры (SQLAlchemy,
uvicorn, aiohttp, alembic) проходят через ту же цепочку процессоров —
иначе половина вывода в проде осталась бы неструктурированной.

Соглашение по вызовам: первый аргумент — стабильный идентификатор события
(``"message.send_failed"``), всё переменное уходит в именованные поля
(``chat_id=...``), а не в текст сообщения.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from typing import TYPE_CHECKING, Any

from pydantic_core import MultiHostHost, MultiHostUrl
import structlog

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from vkt_bot.config import VktSettings

#: Логгеры приложения — им ставится уровень из ``LOGGING``.
APP_LOGGERS = ("vkt_bot", "vkt_dispatcher", "vkteams_client", "vkt_gitlab")

#: Уровни, которыми глушится чужой шум. Перебиваются через ``LOG_LEVELS``.
DEFAULT_LEVELS = {
    "passlib": "ERROR",
    # Свою строку про запрос пишет RequestContextMiddleware, штатный
    # access-лог был бы дублем.
    "uvicorn.access": "WARNING",
    "aiosqlite": "WARNING",
    "multipart": "WARNING",
}

MASK = "***"
#: Подстроки в имени поля, после которых значение в лог не попадает.
SECRET_KEY_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "credential",
)
#: Секрет в query-строке (``?token=001.0000...``) — маскируется по значению:
#: имя поля здесь безобидное (``url``), а токен внутри настоящий.
SECRET_QUERY_RE = re.compile(
    r"((?:token|api_key|apikey|password)=)[^&\s\"']+", re.IGNORECASE
)
#: Глубже вложенности маскировать не пытаемся — процессор работает на каждой
#: строке лога, а секретов на седьмом уровне не бывает.
MAX_MASK_DEPTH = 6


# --------------------------------------------------------------------------- #
# Маскирование
# --------------------------------------------------------------------------- #


def mask_string(url: str) -> str:
    """Заменить строку звёздочками, сохранив длину."""
    return "*" * len(url)


def mask_url(url: str | MultiHostUrl) -> str:
    """Скрыть пароль в DSN, оставив схему, хост, порт и базу."""
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


def is_secret_key(key: str) -> bool:
    """Похоже ли имя поля на секрет."""
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def mask_value(value: Any, depth: int = 0) -> Any:  # noqa: ANN401
    """Замаскировать секреты внутри произвольной структуры."""
    if depth >= MAX_MASK_DEPTH:
        return value
    if isinstance(value, dict):
        return {
            # Маскируется только текст: под «секретным» именем регулярно
            # оказывается что-то безобидное (``access_token_expire_minutes``
            # — это число минут), и звёздочки вместо него только мешают.
            key: MASK
            if is_secret_key(str(key)) and isinstance(val, (str, bytes))
            else mask_value(val, depth + 1)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [mask_value(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_value(item, depth + 1) for item in value)
    if isinstance(value, str):
        return SECRET_QUERY_RE.sub(rf"\1{MASK}", value)
    return value


def mask_secrets(
    logger: Any,  # noqa: ANN401, ARG001
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Процессор: убрать секреты по имени поля и из query-строк.

    Работает на каждой строке, а не только при старте: токен приезжает в
    логи из URL ответов API, где имя поля ничего не подсказывает.
    """
    return mask_value(dict(event_dict))


# --------------------------------------------------------------------------- #
# Процессоры
# --------------------------------------------------------------------------- #


def service_context(service: str, env: str, version: str) -> Any:  # noqa: ANN401
    """Процессор, добавляющий постоянные поля сервиса."""

    def processor(
        logger: Any,  # noqa: ANN401, ARG001
        method_name: str,  # noqa: ARG001
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", env)
        event_dict.setdefault("version", version)
        return event_dict

    return processor


def copy_event_to_message(
    logger: Any,  # noqa: ANN401, ARG001
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Продублировать ``event`` в ``message``.

    ``event`` — стабильный идентификатор (``message.send_failed``), по нему
    фильтруют в LogQL. Grafana же выводит в строке поле ``message``: без
    дубля панель логов показывала бы сырой JSON.
    """
    if "event" in event_dict:
        event_dict.setdefault("message", event_dict["event"])
    return event_dict


# --------------------------------------------------------------------------- #
# Уровни
# --------------------------------------------------------------------------- #


def parse_log_levels(raw: str) -> tuple[dict[str, str], list[str]]:
    """Разобрать ``"sqlalchemy.engine=WARNING,aiohttp=DEBUG"``.

    Возвращает пару «уровни, непонятые куски». Кривая запись не роняет
    процесс, но и не пропадает молча: о ней пишется предупреждение сразу
    после настройки логирования.
    """
    levels: dict[str, str] = {}
    problems: list[str] = []
    known = logging.getLevelNamesMapping()

    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        name, separator, level = item.partition("=")
        name, level = name.strip(), level.strip().upper()
        if not separator or not name or level not in known:
            problems.append(item)
            continue
        levels[name] = level

    return levels, problems


def apply_levels(settings: VktSettings) -> list[str]:
    """Расставить уровни логгеров. Возвращает непонятые куски ``LOG_LEVELS``."""
    overrides, problems = parse_log_levels(settings.log_levels)
    levels: dict[str, str] = {name: settings.logging for name in APP_LOGGERS}
    levels.update(DEFAULT_LEVELS)
    levels.update(overrides)

    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)

    return problems


# --------------------------------------------------------------------------- #
# Сборка
# --------------------------------------------------------------------------- #


def use_json(log_format: str) -> bool:
    """Нужен ли JSON-рендерер.

    ``auto`` — человеку в терминале консольный формат, всему остальному
    (контейнер, systemd, CI) JSON.
    """
    if log_format == "json":
        return True
    if log_format == "console":
        return False
    return not sys.stdout.isatty()


def build_processors(
    *, json_output: bool, service: str, env: str, version: str
) -> list[Any]:
    """Общая цепочка процессоров для structlog и для чужих логгеров."""
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if json_output:
        # В консоли постоянные поля сервиса — визуальный мусор: и так видно,
        # какой процесс запущен.
        processors += [service_context(service, env, version), copy_event_to_message]
    # Маскирование — последним: к этому моменту все поля уже собраны.
    processors.append(mask_secrets)
    return processors


def build_formatter(
    *, json_output: bool, colors: bool, processors: list[Any]
) -> structlog.stdlib.ProcessorFormatter:
    """Форматтер для handler'а: он же рендерит записи сторонних логгеров."""
    if json_output:
        renderers: list[Any] = [
            # Трейсбек — поле, а не многострочный хвост: promtail режет
            # многострочный вывод на отдельные «записи». Локальные
            # переменные кадров выключены: они раздувают строку и тащат в
            # лог всё, что случайно оказалось в области видимости.
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            ),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    else:
        renderers = [structlog.dev.ConsoleRenderer(colors=colors)]

    return structlog.stdlib.ProcessorFormatter(
        # Записи чужих логгеров прогоняются через ту же цепочку плюс
        # ExtraAdder: библиотеки передают структурные поля через ``extra``.
        foreign_pre_chain=[structlog.stdlib.ExtraAdder(), *processors],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *renderers,
        ],
    )


def init_logging() -> None:
    """Настроить логирование по текущим настройкам."""
    import vkt_bot
    from vkt_bot.config import get_settings

    settings = get_settings()
    json_output = use_json(settings.log_format)
    processors = build_processors(
        json_output=json_output,
        service=settings.service_name,
        env=settings.env,
        version=vkt_bot.__version__,
    )

    structlog.configure(
        processors=[
            *processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        # stdlib-обёртка, а не filtering_bound_logger: уровни нужны
        # по-логгерно (``LOG_LEVELS``), а фильтрующая обёртка знает только
        # один общий уровень.
        wrapper_class=structlog.stdlib.BoundLogger,
        # Кэш выключен намеренно: с ним ``structlog.testing.capture_logs``
        # не видит уже созданные логгеры. Объём логов у бота не тот, чтобы
        # экономить на связывании.
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(
        build_formatter(
            json_output=json_output,
            colors=not json_output and sys.stdout.isatty(),
            processors=processors,
        )
    )
    root.addHandler(stream)
    # Чужие логгеры по умолчанию молчат до предупреждений; свои поднимаются
    # до ``LOGGING`` в apply_levels, остальное — через ``LOG_LEVELS``.
    root.setLevel(logging.WARNING)

    if settings.log_file:
        if not settings.log_file.parent.exists():
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file.absolute(), maxBytes=1_000_000, backupCount=3
        )
        # В файл всегда JSON: его читают программы, а не человек.
        file_handler.setFormatter(
            build_formatter(
                json_output=True,
                colors=False,
                processors=build_processors(
                    json_output=True,
                    service=settings.service_name,
                    env=settings.env,
                    version=vkt_bot.__version__,
                ),
            )
        )
        root.addHandler(file_handler)

    problems = apply_levels(settings)
    log_startup(settings, json_output=json_output, level_problems=problems)


def log_startup(
    settings: VktSettings, *, json_output: bool, level_problems: list[str]
) -> None:
    """Записать версию и настройки — с замаскированными секретами."""
    import vkt_bot

    logger = structlog.get_logger("vkt_bot.settings")
    if level_problems:
        logger.warning("settings.log_levels_invalid", chunks=level_problems)

    values = settings.model_dump()
    # Пароль в DSN маскируется отдельно: имя поля ``db_url`` секретным не
    # выглядит, а хост и базу в логе видеть хочется.
    if values.get("db_url"):
        values["db_url"] = mask_url(values["db_url"])
    # Остальные секреты снимет процессор ``mask_secrets``; незаданные поля
    # он не тронет — их видно как ``None``.
    logger.info(
        "app.settings",
        version=vkt_bot.__version__,
        log_format="json" if json_output else "console",
        settings=values,
    )


def setup_sentry() -> None:
    """Поднять Sentry, если задан DSN.

    Логи уровня ERROR доезжают до Sentry сами: записи идут через stdlib,
    а его интеграция включена в SDK по умолчанию. Здесь добавляется
    окружение и версия — без них события всех стендов сваливаются в одну
    кучу.
    """
    import vkt_bot
    from vkt_bot.config import get_settings

    settings = get_settings()
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            settings.sentry_dsn,
            environment=settings.env,
            release=vkt_bot.__version__,
        )
