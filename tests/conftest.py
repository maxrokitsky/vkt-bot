"""Общие фикстуры.

Переменные окружения выставляются до импорта любого модуля ``vkt_bot``,
поэтому настройки в тестах детерминированы и не зависят от локального
``.env``.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
from typing import TYPE_CHECKING, Any

TEST_ENV = {
    "LOGGING": "DEBUG",
    "BOT_TOKEN": "001.0000000000.0000000000:000000000",
    "DB_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/vkt_bot_test",
    "SECRET_KEY": "test-secret-key",
    "OWNER_ID": "owner@example.com",
    "PUBLIC_URL": "https://panel.example.com",
    # Настройки плагинов тоже фиксируем: у ``AiSettings`` свой
    # ``env_file=".env"``, и без этого тесты читали бы боевой ключ и
    # включённого агента с машины разработчика.
    "AI_ENABLED": "false",
    "AI_API_KEY": "",
    "AI_MODEL": "test/model",
    "AI_REPLY_ON_REPLY": "true",
}
for _key, _value in TEST_ENV.items():
    os.environ[_key] = _value
for _key in ("SENTRY_DSN", "LOG_FILE"):
    os.environ.pop(_key, None)

import pytest  # noqa: E402
import sqlalchemy as sa  # noqa: E402
import structlog  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from vkteams_client.types import (  # noqa: E402
    MsgResponse,
    ThreadSubscribersResponse,
)

from vkt_bot.db.base import Model  # noqa: E402
from vkt_bot.db.session import async_session  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytest_plugins = ("tests.factories",)


@pytest.fixture(scope="session", autouse=True)
def _configure_structlog() -> None:
    """Направить structlog в стандартный ``logging``.

    В приложении это делает ``init_logging``, но в тестах он подменён:
    перенастройка logging сломала бы вывод pytest. Без конфигурации
    structlog пишет своим ``PrintLogger`` мимо stdlib — и ни ``caplog``,
    ни уровни логгеров не работают.

    Рендерер здесь ``KeyValueRenderer``, а не боевой ``ProcessorFormatter``:
    тогда ``caplog.text`` — это строка, в которой видно и имя события, и
    поля. Боевую цепочку проверяет ``tests/utils/test_logging.py``.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.KeyValueRenderer(key_order=["event"]),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


@pytest.fixture(autouse=True)
def _clear_log_context() -> Iterator[None]:
    """Не давать контексту логирования протекать между тестами."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Импортировать все модели, чтобы ``Model.metadata`` была полной."""
    import importlib

    importlib.import_module("vkt_bot.core.models")
    importlib.import_module("vkt_gitlab.models")
    importlib.import_module("vkt_ai.models")


# --------------------------------------------------------------------------- #
# База данных
# --------------------------------------------------------------------------- #


def _test_db_url(tmp_dir: pathlib.Path) -> str:
    """DSN тестовой базы.

    ``TEST_DB_URL`` переопределяет базу (в CI туда подставляется PostgreSQL).
    По умолчанию — файловый SQLite, чтобы ``pytest`` запускался без внешних
    сервисов.
    """
    return os.environ.get("TEST_DB_URL") or f"sqlite+aiosqlite:///{tmp_dir / 'test.db'}"


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    """DSN тестовой базы."""
    with tempfile.TemporaryDirectory(prefix="vkt-bot-tests-") as tmp:
        yield _test_db_url(pathlib.Path(tmp))


@pytest.fixture(scope="session")
def is_postgres(db_url: str) -> bool:
    """Тесты идут на настоящем PostgreSQL."""
    return db_url.startswith("postgresql")


def _fix_sqlite_transactions(engine: AsyncEngine) -> None:
    """Заставить pysqlite вести транзакции честно и проверять внешние ключи.

    Драйвер по умолчанию сам решает, когда открывать транзакцию, из-за чего
    ``RELEASE SAVEPOINT`` коммитит внешнюю транзакцию и откат после теста
    перестаёт работать. Рецепт из документации SQLAlchemy.

    ``PRAGMA foreign_keys`` в SQLite по умолчанию **выключена**, и без неё
    локальный прогон мягче боевого PostgreSQL: нарушение внешнего ключа
    проходит молча и всплывает только в CI. Один такой баг так и нашёлся —
    сессия агента вставлялась раньше участника, на которого ссылается.
    Пусть тесты будут строгими там же, где строгая база.
    """

    @sa.event.listens_for(engine.sync_engine, "connect")
    def _disable_implicit_begin(dbapi_connection: Any, record: Any) -> None:  # noqa: ANN401, ARG001
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        # Только вне транзакции: внутри неё PRAGMA молча ничего не делает.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @sa.event.listens_for(engine.sync_engine, "begin")
    def _explicit_begin(conn: Any) -> None:  # noqa: ANN401
        conn.exec_driver_sql("BEGIN")


@pytest.fixture(scope="session")
async def engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    """Движок тестовой базы со созданной схемой."""
    engine = create_async_engine(db_url)
    if db_url.startswith("sqlite"):
        _fix_sqlite_transactions(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Соединение во внешней транзакции, которая откатывается после теста."""
    conn = await engine.connect()
    transaction = await conn.begin()
    try:
        yield conn
    finally:
        if transaction.is_active:
            await transaction.rollback()
        await conn.close()


@pytest.fixture
def session_factory(
    connection: AsyncConnection,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Фабрика сессий, привязанная к откатываемому соединению.

    ``join_transaction_mode="create_savepoint"`` превращает ``commit()``
    внутри тестируемого кода в снятие SAVEPOINT, поэтому данные видны
    внутри теста и исчезают после него.
    """
    factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async_session.configure(factory=factory)
    try:
        yield factory
    finally:
        async_session.reset()


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Сессия для самого теста."""
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
async def _no_global_session_factory() -> AsyncIterator[None]:
    """Не давать тестам без фикстуры БД случайно открыть настоящее соединение.

    ``reset`` не закрывает движок сам, поэтому сначала отдаём пул: иначе
    тест, дошедший до фолбэка на ``settings.db_url``, оставил бы за собой
    незакрытые соединения.
    """
    yield
    await async_session.dispose()
    async_session.reset()


# --------------------------------------------------------------------------- #
# Бот
# --------------------------------------------------------------------------- #


class BotCall:
    """Один вызов метода API у фейкового бота."""

    def __init__(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]):
        self.method = method
        self.args = args
        self.kwargs = kwargs

    def arg(self, index: int, name: str, default: Any = None) -> Any:  # noqa: ANN401
        """Аргумент, переданный позиционно или по имени."""
        if name in self.kwargs:
            return self.kwargs[name]
        if index < len(self.args):
            return self.args[index]
        return default

    @property
    def chat_id(self) -> Any:  # noqa: ANN401
        """``chat_id`` вызова."""
        return self.arg(0, "chat_id")

    @property
    def text(self) -> Any:  # noqa: ANN401
        """``text`` вызова."""
        return self.arg(1, "text")

    def __repr__(self) -> str:
        return f"BotCall({self.method}, args={self.args!r}, kwargs={self.kwargs!r})"


class FakeBot:
    """Шпион вместо ``VKTeams``: запоминает вызовы, ничего не отправляет."""

    def __init__(self) -> None:
        self.calls: list[BotCall] = []
        self.errors: dict[str, BaseException] = {}
        self.results: dict[str, Any] = {
            # Настоящий клиент на успешную отправку возвращает msgId, и от
            # него зависит логика: якорь обсуждения, запись своих
            # сообщений в историю. Без ответа по умолчанию тесты
            # проверяли бы поведение при отказе сервера.
            "send_text": MsgResponse(ok=True, msgId="bot-msg-1"),
            "edit_text": MsgResponse(ok=True, msgId="bot-msg-1"),
            # Так API отвечает на ``threads/subscribers/get`` для обычного
            # чата. Через эту проверку проходит каждое сообщение: по виду
            # ``chatId`` тред от группы не отличить. Обсуждение задаётся
            # ответом ``ok=True``.
            "threads_subscribers_get": ThreadSubscribersResponse(
                ok=False, description="Incorrect threadId"
            ),
        }

    def _record(
        self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Any:  # noqa: ANN401
        call = BotCall(method, args, kwargs)
        self.calls.append(call)
        if method in self.errors:
            raise self.errors[method]
        return self.results.get(method)

    def calls_of(self, method: str) -> list[BotCall]:
        """Все вызовы конкретного метода."""
        return [c for c in self.calls if c.method == method]

    @property
    def sent(self) -> list[BotCall]:
        """Вызовы ``send_text``."""
        return self.calls_of("send_text")

    @property
    def texts(self) -> list[str]:
        """Тексты отправленных сообщений."""
        return [call.text for call in self.sent]

    def __getattr__(self, method: str) -> Any:  # noqa: ANN401
        if method.startswith("_"):
            raise AttributeError(method)

        async def call(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            return self._record(method, args, kwargs)

        return call


@pytest.fixture
def fake_bot() -> FakeBot:
    """Фейковый бот-шпион."""
    return FakeBot()


@pytest.fixture
def dispatcher(fake_bot: FakeBot) -> Any:  # noqa: ANN401
    """Чистый диспетчер с фейковым ботом (без глобальных хендлеров)."""
    from vkt_dispatcher import Dispatcher

    return Dispatcher(bot=fake_bot)  # type: ignore[arg-type]


@pytest.fixture
def patched_bot(fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch) -> FakeBot:
    """Подменить глобальный ``vkt_bot.app.bot`` фейковым.

    Роутеры и плагины импортируют ``bot`` по имени, поэтому патчим каждое
    место импорта.
    """
    import vkt_bot.app

    monkeypatch.setattr(vkt_bot.app, "bot", fake_bot, raising=False)
    for module in (
        "vkt_bot.webapp.api.chats",
        "vkt_bot.webapp.api.webhooks",
        "vkt_gitlab.api",
    ):
        import importlib

        mod = importlib.import_module(module)
        monkeypatch.setattr(mod, "bot", fake_bot, raising=False)
    return fake_bot


# --------------------------------------------------------------------------- #
# Настройки
# --------------------------------------------------------------------------- #


@pytest.fixture
def settings() -> Any:  # noqa: ANN401
    """Настройки приложения (единый закэшированный объект)."""
    from vkt_bot.config import get_settings

    return get_settings()


@pytest.fixture
def owner_id(settings: Any) -> str:  # noqa: ANN401
    """ID владельца бота из настроек."""
    return settings.owner_id


# --------------------------------------------------------------------------- #
# Веб-приложение
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def app() -> Any:  # noqa: ANN401
    """FastAPI-приложение со всеми роутерами и плагинами.

    ``init_logging`` подменяется: перенастройка logging сломала бы вывод
    pytest.
    """
    import vkt_bot
    import vkt_bot.webapp.app as webapp_app

    original_init_logging = vkt_bot.init_logging
    vkt_bot.init_logging = lambda: None  # type: ignore[assignment]
    try:
        return webapp_app.create_app()
    finally:
        vkt_bot.init_logging = original_init_logging  # type: ignore[assignment]


@pytest.fixture
async def client(
    app: Any,  # noqa: ANN401
    session_factory: async_sessionmaker[AsyncSession],  # noqa: ARG001
) -> AsyncIterator[Any]:
    """HTTP-клиент к приложению без сети (ASGITransport)."""
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


def auth_headers(user_id: str) -> dict[str, str]:
    """Заголовок Authorization с валидным JWT для указанного пользователя."""
    from vkt_bot.webapp.api.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token(data={'sub': user_id})}"}


@pytest.fixture
def make_auth_headers() -> Any:  # noqa: ANN401
    """Фабрика заголовков авторизации."""
    return auth_headers


# --------------------------------------------------------------------------- #
# Прочее
# --------------------------------------------------------------------------- #


async def table_count(session: AsyncSession, model: type[Model]) -> int:
    """Количество строк в таблице модели."""
    return await session.scalar(sa.select(sa.func.count()).select_from(model)) or 0
