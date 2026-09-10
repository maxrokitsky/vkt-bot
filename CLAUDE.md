# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## О проекте

Бот для VK Teams: инструменты для удобства мессенджера и интеграции с другими
системами. Python 3.13+, пакетный менеджер — **uv**.

Репозиторий — **uv workspace**:

- `src/vkt_bot/` — само приложение: обработчики событий, БД, веб-API;
- `packages/vkt-dispatcher/` — фреймворк: жизненный цикл бота, хендлеры,
  middleware, фильтры;
- `packages/vkteams-client/` — асинхронный клиент VK Teams Bot API на aiohttp
  с pydantic-моделями;
- `plugins/vkt-gitlab/` — плагин GitLab (уведомления о пайплайнах);
- `control-panel-app/` — панель управления на Vue 3, свой `package.json` и
  свой [CLAUDE.md](control-panel-app/CLAUDE.md).

Спецификация API: <https://teams.vk.com/botapi/> (`api.yaml`, `schemas.json`,
`params.json`, описания методов — в `lang_config_ru.json`). Это единственный
источник правды по методам; сторонние обёртки не цитируем.

## Команды

```bash
uv run bot            # бот: опрос событий (make bot)
uv run server         # FastAPI на 0.0.0.0:8765 (make server)
uv run shell          # IPython с готовой сессией БД
uv sync               # синхронизация зависимостей
uv add <package>      # зависимость в основной проект (--dev — в dev-группу)
```

Инструменты живут только в окружении проекта: `ruff`, `alembic` и `pytest`
без `uv run` в PATH не найдутся.

```bash
uv run ruff check .          # линт
uv run ruff check --fix .    # автопочинка
uv run ruff format .         # форматирование
uv run ruff format --check . # проверка формата (так делает CI)
```

Миграции (Alembic, `src/vkt_bot/migrations/`, конфиг в `pyproject.toml`,
post-write hook форматирует файл через ruff):

```bash
uv run alembic upgrade head                          # применить
uv run alembic revision --autogenerate -m "message"  # сгенерировать
make migrate                                         # то же, что upgrade head
```

Схема API и клиент фронтенда:

```bash
make export_schema    # openapi.json из приложения
make generate_client  # export_schema + pnpm openapi-ts в control-panel-app
```

База для разработки: `docker-compose up postgres-db` (порт 16432→5432).

## Тесты

pytest + pytest-asyncio (`asyncio_mode = "auto"`, тесты и фикстуры живут в
одном event loop уровня сессии).

```bash
uv run pytest                       # весь набор + отчёт покрытия
uv run pytest tests/client -q       # один раздел
uv run pytest --no-cov              # без покрытия (быстрее)

# один тест: путь::класс::метод — или отбор по имени через -k
uv run pytest tests/handlers/test_roles.py::TestNotifyRoleIsTagged -q --no-cov
uv run pytest -k "thread and forward" --no-cov
```

### База данных в тестах

По умолчанию — файловый SQLite, внешние сервисы не нужны. `TEST_DB_URL`
переключает на настоящий PostgreSQL (так делает CI):

```bash
docker compose up -d postgres-db
createdb -h localhost -p 16432 -U postgres vkt_bot_test
TEST_DB_URL=postgresql+psycopg://postgres@localhost:16432/vkt_bot_test uv run pytest
```

Только на PostgreSQL идут: smoke-тест миграций (`tests/db/test_migrations.py`,
маркер `postgres`), `ilike` по кириллице и приведение строк к `UUID`.

Изоляция — через внешнюю транзакцию: `conftest.py` открывает соединение,
привязывает к нему фабрику сессий (`join_transaction_mode="create_savepoint"`)
и откатывает всё после теста. Поэтому `commit()` внутри тестируемого кода
виден внутри теста и исчезает после него.

### Устройство `tests/`

- `conftest.py` — окружение, БД, `FakeBot` (шпион вместо `VKTeams`),
  `app`/`client` для FastAPI, заголовки авторизации;
- `factories.py` — загрузка событий из `tests/fixtures/events/*.json` и
  фабрики моделей;
- разделы: `client/`, `dispatcher/`, `db/`, `webapp/`, `handlers/`,
  `plugins/`, `core/`, `utils/`.

### Тестируемость

- Настройки читаются лениво: `vkt_bot.config.get_settings()` (кэш через
  `lru_cache`), модульный `settings` резолвится по первому обращению. Импорт
  любого модуля `vkt_bot.*` не требует `.env` и не завершает процесс.
- Единственная точка выхода при неполной конфигурации — `main.check_settings()`.
- `vkt_bot.db.session.async_session` — ленивая фабрика: `configure(url=...)`
  или `configure(factory=...)` подменяет базу для всех модулей сразу,
  `create_session_factory(url)` собирает движок и фабрику вручную.
- Миграции принимают DSN из `ALEMBIC_DB_URL` (иначе берут `settings.db_url`).

### Покрытие и известные дефекты

Порог — 70% (`--cov-fail-under=70`), фактическое покрытие ~97%. Coverage
настроен с `concurrency = ["thread", "greenlet"]`: без этого трассировка
теряется внутри корутин, которые ходят в БД через greenlet SQLAlchemy.

Строгие `xfail` фиксируют сломанное поведение и позеленеют после починки:
11 фильтров в `vkt_dispatcher.filters` читают несуществующий `event.data`
(ROADMAP 3.1).

## CI

`.github/workflows/`: `lint.yml` (`ruff check .` и `ruff format --check .`),
`test.yml` (`uv run pytest` с PostgreSQL в service-контейнере), `build.yml`.
Тайпчекера нет — ошибки сигнатур вроде «неизвестный именованный аргумент»
ловятся только тестами.

## Архитектура

### События и хендлеры

1. **Опрос**: `Dispatcher.start_polling()` тянет события из VK Teams. Сетевые
   ошибки (`TimeoutError`, `OSError`, `aiohttp.ClientError`) гасятся повтором
   с нарастающей паузой (`Dispatcher.RETRY_DELAYS`) — long-poll регулярно
   отваливается по таймауту, и раньше это завершало процесс бота. Ошибки в
   коде по-прежнему поднимаются наружу и роняют polling.
2. **Маршрутизация**: `Dispatcher.trigger(event)` применяет middleware и
   опрашивает хендлеры.
3. **Выполнение**: подошедшие хендлеры работают параллельно в
   `asyncio.TaskGroup`.

Регистрация: хендлеры подхватываются импортом своих модулей
(`src/vkt_bot/core/handlers/`), у плагинов — из `install()`.

Базовые классы (`vkt_dispatcher.handlers`): `MessageHandler`,
`CommandHandler`, `BotButtonCommandHandler`, `NewChatMembersHandler`,
`LeftChatMembersHandler`, `ChangedChatInfoHandler`, `EditedMessageHandler`,
`DeletedMessageHandler`, `PinnedMessageHandler`, `UnPinnedMessageHandler`.

Фильтры из `vkt_dispatcher.filters` комбинируются операторами `&`, `|`, `~` —
например `Filter.command & Filter.private`.

### Учёт чатов (`core/handlers/chats.py`)

- Чат записывается, как только бота в него добавили (`newChatMembers`), и
  дополнительно на первом сообщении (`CreateChatMiddleware`) — для чатов, куда
  бот попал раньше.
- Когда добавляют самого бота, состав забирается через `chats/getMembers`:
  по участникам, вступившим до нас, событий не будет. У `get_members` пока нет
  курсора, поэтому очень большие чаты API обрезает (ROADMAP 3.6).
- `chat_memberships` следует за `newChatMembers` / `leftChatMembers`, но строка
  `ChatUser` после ухода остаётся: у человека могут быть роли и другие чаты.
- Имена (`first_name`, `last_name`, `nick`) приходят только из событий —
  их несут объекты `User` и `Bot`, а `chats/getMembers` отдаёт голые id.
  Каждое сообщение обновляет имя отправителя (`CreateChatMiddleware`, только
  update: поток сообщений строк `ChatUser` не создаёт). Пока участник из
  ростера не появится в событии, `ChatUser.display_name` показывает id. Пустое
  значение никогда не затирает известное.
- Боты — обычные участники с `ChatUser.is_bot = True`. Флаг ставится только из
  события, где боты приходят отдельным типом, поэтому бот, сидевший в чате до
  нашего, числится обычным пользователем, пока где-нибудь не засветится.
  Снятым флаг не бывает.

### Обсуждения — threads (`core/threads.py`, `core/handlers/threads.py`)

- У обсуждения собственный `chatId`, отдельных типов событий нет: сообщение
  из треда приходит обычным `newMessage` с `chatId` треда. Отправка в тред —
  тот же `send_text` с `chat_id=thread_id`.
- **По виду `chatId` тред от обычной группы не отличить** — в документации
  пример `2601@chat.agent`, но живой тред получился `693938330@chat.agent`
  при родителе `694348323@chat.agent`. Определять тред регекспом по id
  нельзя; единственная проверка — `threads/subscribers/get`, который для
  обычного чата отказывает с `Incorrect threadId` (`core/handlers/roles.py`,
  `thread_subscribers`). Проверка стоит запроса к API, поэтому фильтром
  уровня диспетчера её делать не стоит.
- **`threads/add` работает как get-or-create** (проверено 2026-09-10): три
  вызова на одном `(chatId, msgId)` вернули один и тот же `threadId`, без
  ошибок и дублей. Это единственный способ узнать id уже существующего
  обсуждения: в событиях ссылки на тред нет, метода вроде `threads/get` в
  спеке тоже. Обратная сторона — вызов не только читает: у сообщения без
  обсуждения он его создаст. Обёртка — `core.threads.get_or_create_thread`.
  Отсюда же вывод: соответствие «сообщение → тред» хранить у себя не надо,
  достаточно `msgId` сообщения-якоря. Вложенных обсуждений нет — с `chatId`
  треда метод отвечает `Bad request`.
- События из треда доходят только подписчикам. Поэтому при добавлении бота в
  чат (`ChatMembersJoinedHandler`) вызывается `threads/autosubscribe` с
  `withExisting=true` — подписка и на будущие, и на существующие обсуждения.
- Автоподписку можно выключить глобально настройкой `threads_autosubscribe`
  в `bot_settings` (`false`/`0`/`no`/`off`; по умолчанию включено), а для
  отдельного чата — командой `/subscribethreads off` (админ). Обратно
  включается `/subscribethreads` — она же нужна для чатов, где бот сидел ещё
  до появления автоподписки.
- Призыв по роли (`#роль`) работает в обсуждениях без отдельного кода:
  обработчик ловит любой `newMessage`. У чата-треда в событии `title` пустой,
  поэтому название берётся из события, затем из таблицы `chats`, а если его
  нет нигде — пишем «Вас упомянули» без имени чата.
- **Пересылка сообщений из треда API не поддерживается** — проверено на живом
  стенде 2026-09-09: `forwardChatId` с id треда даёт `Bad request` при
  пересылке в личку, в родительский чат и в сам тред, для сообщений и в чужом,
  и в собственноручно созданном треде. `forwardChatId` родителя с `msgId` из
  треда — `msgId not found`. Из обычного чата пересылка работает.
  `replyMsgId` внутри треда — тоже `Bad request`. У треда работают только
  `messages/sendText` (включая упоминания `@[user_id]`) и группа `threads/*`;
  `chats/getInfo` и `chats/getMembers` недоступны.
- Поэтому `NotifyRoleIsTaggedHandler` сначала пробует пересылку (в обычных
  чатах она проходит), а на отказ отправляет второе сообщение — уведомление
  плюс автор и текст исходного сообщения.
- Текст в это второе сообщение попадает не всем: роль глобальна, и её
  носитель может не состоять в чате-источнике. Для обычного чата состав
  берётся из `chat_memberships`, и посторонний получает уведомление без
  текста. **В обсуждении проверять нечем**, поэтому текст уходит всем
  носителям роли. Подписчики треда для этого не годятся: подписка опт-ин
  (`threads/subscribers/get` отдаёт бота и тех, кто в обсуждение уже влез),
  а читать тред может любой участник родительского чата — сверка с этим
  списком отказывала почти всем. Родительский чат по треду не узнать:
  ссылки на него нет ни в событии, ни в API.
- Тред от обычного чата отличает `NotifyRoleIsTaggedHandler.is_thread`:
  `threads/subscribers/get` с `pageSize=1` — нужен только факт, а не список.
  Отказ `Incorrect threadId` ожидаем (через проверку идёт каждое сообщение
  обычного чата) и пишется в debug, любой другой — в warning. При сбое
  считаем чат обычным: проверка по членству строже.
- Клиент: `threads_add`, `threads_autosubscribe`, `threads_subscribers_get`
  и `iter_thread_subscribers` (автопагинация по `cursor`).
- В спеке у тредов ровно три метода (`add`, `autosubscribe`,
  `subscribers/get`), и `threadId` возвращает только `threads/add`.
  Корневой `api.yaml` обновлён 2026-09-10 отсюда:
  `https://teams.vk.com/botapi/{api.yaml,schemas.json,params.json,lang_config_ru.json}`.

### Ответы API

`send_text`, `edit_text` и `send_file` возвращают `MsgResponse`. При
`ok: false` исключения нет — есть `description` с причиной и запись уровня
ERROR в лог. Раньше `ok` не проверялся вовсе, и отказ выглядел в логах как
успешная отправка: сообщение «отправлено», а до адресата не дошло. Причины
отказов ищите в логгере `vkteams_client.send_message`.

### Плагины

Автообнаружение через entry points:

1. В `pyproject.toml` плагина:
   ```toml
   [project.entry-points.'vkt_bot.plugins']
   plugin_name = "module_path"
   ```
2. В модуле — функция `install()`, которая импортирует `models` (регистрация
   ORM-моделей), `handlers` и, если нужно, `api` с роутерами FastAPI.
3. Плагин подхватывается при старте бота через `importlib.metadata.entry_points`.

### Работа с БД

SQLAlchemy 2.0 (async), три слоя:

- **модели** — `src/vkt_bot/core/models/`;
- **репозитории** — `src/vkt_bot/core/repositories/`, наследуют
  `AsyncRepository[Model, PK, CreateSchema, UpdateSchema]` (дженерики
  выводятся автоматически);
- **запросы** — `src/vkt_bot/core/queries/`, реализуют протокол `Query` с
  методом `apply(stmt)` и комбинируются: `repository.query(Q1(), Q2())`.

Сессии: в хендлерах бота — `async_session()` вручную, в веб-API — через
зависимость `get_session()` из `webapp/dependencies.py`.

### Веб-приложение (`src/vkt_bot/webapp/`)

FastAPI. `app.py` собирает роутеры, `api/` — эндпоинты, `schemas/` — pydantic,
`dependencies.py` — внедрение зависимостей. Документация на `/docs` и `/redoc`.

Из неочевидного:

- `api/overview.py` — счётчики и активность по дням для главной страницы.
  Активность собирается из `log_entries` группировкой по `date(timestamp)`
  (работает и в SQLite, и в PostgreSQL — типы возврата разные, приводятся в
  `as_date`) и отдаётся только админам: журнал остальным недоступен.
- `api/webhooks.py` — CRUD плюс отдельный публичный роутер для входящих
  вызовов.
- `api/chats.py` — у детали чата есть счётчики участников и вебхуков, а
  `GET /api/chats/{id}/webhooks` отдаёт вебхуки чата: админу все, остальным
  только свои. Счётчик считает то же, что покажет список, — иначе рядом с
  одной строкой стояло бы «3».
- Состав чата — это `GET /api/chat-users?chat_id=...`: фильтр идёт через
  `chat_memberships`, поэтому ушедшие из списка исчезают, хотя их строки
  `ChatUser` остаются.
- Зависимости доступа: `CurrentUser`, `CurrentAdminUser`, `CurrentOwnerUser`,
  `SessionDep`.

### Вход в панель и права

Логина с паролем нет — панель авторизует бот. Команда `/login` в VK Teams
возвращает одноразовый токен (5 минут) и ссылку на
`{PUBLIC_URL}/login?token=...`; токен одноразовый и меняется на JWT в
`POST /api/auth/login`.

Права администратора дают либо `OWNER_ID` в `.env`, совпадающий с id
пользователя VK Teams, либо флаг `is_superuser` в строке `ChatUser`. Строка
создаётся при первом `/login`, и владелец там же получает `is_superuser = True`
(`core/handlers/auth.py`) — права переживут смену `OWNER_ID`. Операция
идемпотентна и попадает в журнал аудита. Отдельной таблицы пользователей нет:
идентичность — это `ChatUser` с id VK Teams в качестве первичного ключа.

### Конфигурация (`.env`, pydantic-settings)

Обязательно: `BOT_TOKEN`, `DB_URL` (DSN PostgreSQL), `LOGGING` (уровень).

Необязательно: `OWNER_ID`, `SECRET_KEY` (нужен для JWT веб-API),
`PUBLIC_URL`, `SENTRY_DSN`, `ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию
8 дней), `LOG_FILE`, `RABBITMQ_LOGGING`, `MAX_FILE_SIZE` и
`ALLOWED_FILE_TYPES` (50 МБ и белый список MIME по умолчанию).

### Логи

Логгеры: `vkt_bot.main` (приложение), `vkt_dispatcher` (фреймворк),
`vkteams_client` с ветками `.events` и `.send_message` (клиент API).
Настройка — `src/vkt_bot/loggers.py` и `src/vkt_bot/utils/log.py`; при
заданном `LOG_FILE` добавляется файловый обработчик, который пишет тела
ответов API в JSON.

## Точки входа

`src/vkt_bot/main.py` (`start_bot`, `start_server`, `shell`, `check_settings`),
`src/vkt_bot/app.py` (глобальные `bot` и `dispatcher`),
`src/vkt_bot/__init__.py` (`setup()`: логи, Sentry, загрузка плагинов).

## Типовые задачи

1. **Новый хендлер** — класс от подходящего базового, регистрация через
   `@dispatcher.register_handler`, модуль в `src/vkt_bot/core/handlers/`
   (не забыть импорт в `handlers/__init__.py`).
2. **Новый плагин** — каталог в `plugins/`, `pyproject.toml` с entry point,
   функция `install()`; подхватится на следующем старте.
3. **Изменение схемы БД** — правка модели, `uv run alembic revision
   --autogenerate -m "..."`, вычитка миграции, `uv run alembic upgrade head`.
4. **Новый эндпоинт** — роут в `webapp/api/`, схемы в `webapp/schemas/`,
   роутер в `webapp/app.py`, `CurrentAdminUser` для админских ручек; после
   правки схем — `make generate_client`, иначе упадёт
   `tests/webapp/test_openapi.py`.

## Развёртывание

`Dockerfile` и `docker-compose.yaml`; сборка через uv с `--all-packages`
(монорепозиторий). PostgreSQL на 16432→5432, конфиг RabbitMQ закомментирован.
Фронтенд собирается в статику через `pnpm build`.
