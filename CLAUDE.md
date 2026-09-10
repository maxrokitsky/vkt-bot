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
- `packages/vkt-agent/` — каркас ИИ-агента: зависимости инструментов,
  политика подтверждений, запуск сессии с лимитами;
- `plugins/vkt-gitlab/` — плагин GitLab (уведомления о пайплайнах);
- `plugins/vkt-ai/` — ИИ-агент (`/ai`), инструменты и фоновые сессии;
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
  `plugins/`, `core/`, `agent/`, `utils/`.

Сети в тестах агента нет: `TestModel` отвечает заглушкой, `FunctionModel`
играет сценарий вызовов. `FunctionModel` без `stream_function` стрим не
поддерживает — а прогресс в чате его включает, поэтому тесты, где нужен
`on_step`, идут либо на `TestModel`, либо со `stream_function`.

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

### История сообщений (`core/messages.py`, таблица `messages`)

Сообщений не хранилось нигде, и прочитать их у Bot API нельзя — метода
вроде `messages/get` в спеке нет. Отсюда два следствия: единственный
источник — то, что мы пишем сами, и история набирается **только вперёд**,
с момента накатывания миграции. Задним числом её не восстановить, и агент
обязан говорить об этом прямо.

- Пишет `CreateChatMiddleware` (`core/handlers/chats.py`): он и так
  вызывается на каждом `newMessage`. Правки и удаления — отдельные
  хендлеры в `core/handlers/messages.py`.
- **Свои сообщения бота в поток событий не приходят**, поэтому клиент
  отдаёт их через `VKTeams.message_sink` — отдельный крючок рядом с
  `event_sink`: полный текст не должен попадать ни в журнал событий, ни в
  логи.
- Внешних ключей нет ни у `chat_id`, ни у `user_id`: у обсуждения свой
  `chatId`, а автора реплики может ещё не быть в `chat_users` — строки там
  заводит поток событий о составе чата, а не поток сообщений.
- Уникальность `(chat_id, msg_id)`: повторная доставка события и правка не
  должны плодить строки. Индекс `(chat_id, ts)` — под единственный горячий
  запрос «последние N сообщений чата».
- **Удалённое сообщение не отдаётся никогда**: `deleted_at` ставится, но ни
  автоконтекст, ни инструменты агента такую строку не покажут. Человек её
  убрал — бот не должен быть способом её прочитать.
- Выключатели: глобальный `messages_history` в `bot_settings` и команда
  `/history off` на отдельный чат (админ).
- Чистка — та же суточная задача, что у журнала событий
  (`core/events/retention.py`): `MESSAGES_RETENTION_DAYS` (30) плюс потолок
  `MESSAGES_MAX_PER_CHAT` на чат. Таблица самая быстрорастущая в системе.
- Вложения в `text` не попадают (`NewMessagePayload` не разбирает `parts`,
  ROADMAP 3.1), поэтому на их месте заглушка `[вложение]`.

### ИИ-агент (`packages/vkt-agent`, `plugins/vkt-ai`)

`/ai вопрос` — агент отвечает текстом или ходит инструментами. Разбор и
решения — в [AGENT.md](AGENT.md).

- **Слоёв два.** `pydantic-ai` отвечает за диалект вызова инструментов у
  провайдера; `vkt-agent` — за то, чего у библиотеки нет: права актора,
  политику подтверждений, лимиты сессии и прогресс в чате. Пакет не
  импортирует `vkt_bot`: всё приезжает через `AgentDeps`.
- **Провайдер** — любой OpenAI-совместимый шлюз, по умолчанию OpenRouter
  (`AI_BASE_URL`). Имя класса модели у pydantic-ai менялось между версиями
  (`OpenAIModel` → `OpenAIChatModel`), поэтому импорт собран в одном месте
  — `vkt_agent/models.py`.
- **Агент крутится в фоновой задаче, не внутри хендлера.**
  `start_polling` делает `await self.trigger(event)` в цикле, а `trigger`
  ждёт закрытия `TaskGroup`: вызов модели на 30 с остановил бы опрос
  событий для всех чатов сразу. Хендлер отвечает «думаю…» и ставит задачу
  через `vkt_ai.tasks.spawn` (ссылки на задачи держатся в множестве —
  иначе GC соберёт задачу посреди работы).
- Фоновая работа плагина цепляется к жизненному циклу бота через
  `core/lifespans.py`: `install()` регистрирует контекстный менеджер,
  `main.main` входит во все зарегистрированные. `uv run server` их не
  поднимает.
- **Права проверяются внутри инструмента по актору**, не по словам модели.
  Флаг `is_admin` считается один раз при старте сессии (владелец,
  `is_superuser` или роль `admin`). Отказ возвращается **результатом**
  инструмента, а не исключением: `ModelRetry` съедал бы попытки и на
  упрямой модели ронял сессию.
- **`chat_messages` — единственный инструмент с риском утечки.** Агент
  доступен всем участникам, поэтому чат проверяется по `chat_memberships`;
  в обсуждении проверять нечем (состав треда у API не спросить,
  родительский чат по треду тоже), поэтому там инструмент отдаёт только
  сам тред.
- **Автоконтекст — недоверенный ввод.** Последние `AI_CONTEXT_MESSAGES`
  сообщений чата обрамляются явным маркером «данные, не инструкции», и то
  же сказано в системном промпте. Порядок частей зафиксирован: системный
  промпт → инструменты → история → вопрос; история волатильна, и раньше
  неё ставить нечего — кэш префикса на шлюзе промахивался бы всегда.
- **Прогресс переводит запрос в стриминг.** `event_stream_handler`
  подставляется только когда прогресс кому-то нужен: `FunctionModel` в
  тестах стрим без `stream_function` не умеет, а список вызванных
  инструментов считается по сообщениям, а не по потоку событий.
- Диалог живёт в обсуждении: `threads/add` на сообщении-ответе (он же
  get-or-create), продолжение ловит `AgentConversationHandler` по
  `thread_id` в `agent_sessions` — один запрос по индексу вместо запроса
  к API.
- **Обращение без команды** (`@бот вопрос`) — тот же обработчик:
  продолжение в треде, упоминание и личка разведены в одном месте, иначе
  «@бот» внутри треда сессии запускал бы второй диалог. Упоминание
  опознаётся по разметке `format.mention` и по тексту (`@[id]`, `@nick`) —
  `parts` клиент не разбирает (ROADMAP 3.1). Совпадение по целому слову:
  у бота имя «Бот», и участник «Боталов» иначе считался бы обращением.
  Ботам не отвечаем никогда — два бота устроили бы вечную переписку.
- Настройки — свой `BaseSettings` с префиксом `AI_` в плагине; выключатель
  на ходу — `ai_enabled` в `bot_settings`. **В тестах они фиксируются в
  `TEST_ENV`**: у `AiSettings` свой `env_file=".env"`, и без этого тесты
  читали бы боевой ключ с машины разработчика.
- Панель: `/api/ai/status`, `/api/ai/sessions`, `/api/ai/usage` — страница
  «ИИ-агент». `status` нужен, чтобы отличить «агента выключили» от «никто
  не спрашивал»: и там, и там пустой список.

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
  Активность собирается из `events` группировкой по `date(ts)` (работает и в
  SQLite, и в PostgreSQL — типы возврата разные, приводятся в `as_date`) и
  отдаётся только админам.
- `api/webhooks.py` — CRUD плюс отдельный публичный роутер для входящих
  вызовов.
- `api/chats.py` — у детали чата есть счётчики участников и вебхуков, а
  `GET /api/chats/{id}/webhooks` отдаёт вебхуки чата: админу все, остальным
  только свои. Счётчик считает то же, что покажет список, — иначе рядом с
  одной строкой стояло бы «3».
- Состав чата — это `GET /api/chat-users?chat_id=...`: фильтр идёт через
  `chat_memberships`, поэтому ушедшие из списка исчезают, хотя их строки
  `ChatUser` остаются.
- `api/ai.py` (плагин) — диалоги с агентом и расход токенов. Админ видит
  всё, обычный участник — только свои сессии: вопрос к агенту говорит о
  человеке не меньше, чем ответ. Автоконтекст из сообщений вырезается
  (`prompts.strip_context`) — иначе панель стала бы вторым способом читать
  чужие чаты, в обход проверок `chat_messages`.
- Зависимости доступа: `CurrentUser`, `CurrentAdminUser`, `CurrentOwnerUser`,
  `SessionDep`.

### События (`core/events/`, таблица `events`)

Журнал того, что произошло: он показывается в панели, в отличие от логов
приложения. Связывает их `trace_id`. План — [EVENTS.md](EVENTS.md).

- **Один вызов на оба журнала:** `await emit(session, EventType.ROLE_ASSIGNED,
  actor=..., chat_id=..., entity=(EntityType.ROLE, id), payload={...})` пишет
  строку в `events` и строку в лог с теми же полями.
- Запись идёт в **сессию действия без `commit`**: событие не должно пережить
  откат того, о чём рассказывает. Поэтому запись сделана неспособной упасть —
  шаблон рендерится через `SafeFormatMap` (недостающее поле даёт «—»),
  `payload` приводится к JSON-совместимому виду, `summary` обрезается.
  Помнить про `flush()` перед `emit`, если нужен автоинкрементный `entity_id`.
- **Тип события** — строка `<домен>.<действие>` из реестра
  (`core/events/registry.py`): у каждого типа есть подпись, шаблон, источник
  по умолчанию, значимость, `persist` и `chat_scoped`. Плагины добавляют свои
  типы через `register()` из `install()` — колонка хранит строку, миграции для
  этого не нужны. Незарегистрированный тип пишется как есть с warning в логе:
  терять событие хуже.
- `persist=False` — событие живёт только в логах (`message.sent`,
  `api.event_received`): поток сообщений раздул бы таблицу быстрее всего
  остального.
- **`summary` рендерится при записи** — в базе лежит готовый текст, поэтому
  старые события переживают переименование и удаление типа.
- `source` (`panel` / `command` / `api` / `bot` / `webhook` / `plugin` /
  `system`) отвечает на вопрос, которого не знает актор: один и тот же человек
  назначает роль и кнопкой в панели, и командой в чате.
- **Внешних ключей у `chat_id` и `actor_id` нет намеренно:** у обсуждения свой
  `chatId`, которого нет в `chats`, а актором бывает внешняя система
  (`Actor.external("gitlab")`).
- Перечисления хранятся как VARCHAR со **значениями** (`values_callable`), а не
  нативным типом PostgreSQL: `ALTER TYPE` умеет мало, а в базе должно лежать
  то же, что отдаёт API.
- Модель называется `EventRecord`, а не `Event`, — иначе путалась бы с
  событием VK Teams в тех же модулях.
- Чистка: раз в сутки фоновая задача (`core/events/retention.py`,
  запускается из `main.main`) удаляет рутинные события старше
  `EVENTS_RETENTION_DAYS`. Предупреждения и ошибки не удаляются никогда —
  именно их ищут, разбирая старый инцидент; `0` выключает чистку.
- Доступ: `/api/events` админу отдаёт всё, обычному участнику — события его
  чатов (`VisibleToUser`, подзапросом, иначе `total` в пагинации врёт) и без
  текстов сообщений (`TEXT_FIELDS`). `/api/chats/{id}/events` — лента чата,
  только типы с `chat_scoped`. `/api/events/types` отдаёт реестр, чтобы фронт
  не держал свой словарь названий.

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
8 дней), `LOG_FILE`, `LOG_FORMAT`, `LOG_LEVELS`, `ENV`, `SERVICE_NAME`,
`EVENTS_RETENTION_DAYS` (90), `MESSAGES_RETENTION_DAYS` (30),
`MESSAGES_MAX_PER_CHAT` (10000), `MAX_FILE_SIZE` и `ALLOWED_FILE_TYPES`
(50 МБ и белый список MIME по умолчанию).

Агент читает свои настройки сам, с префиксом `AI_` (все необязательные,
по умолчанию выключен): `AI_ENABLED`, `AI_BASE_URL`
(`https://openrouter.ai/api/v1`), `AI_API_KEY`, `AI_MODEL`,
`AI_MAX_STEPS` (8), `AI_TIMEOUT_SECONDS` (120), `AI_MAX_CONCURRENT` (3),
`AI_DAILY_TOKEN_BUDGET` (200000), `AI_CONTEXT_MESSAGES` (20),
`AI_CONTEXT_CHARS` (8000), `AI_RETENTION_DAYS` (30).

### Логи

structlog поверх stdlib, настройка — `src/vkt_bot/logging_setup.py`.
Подробности и запросы к Loki — в [docs/logging.md](docs/logging.md).

- Первый аргумент вызова — **стабильный идентификатор события**
  (`message.send_failed`, `chat.bot_added`), всё переменное идёт полями
  (`chat_id=...`). По идентификатору фильтруют в Grafana, поэтому менять
  его нельзя так же легко, как текст.
- Один поток вывода — stdout. `LOG_FORMAT` выбирает рендерер: `console`
  локально, `json` в контейнере, `auto` (по умолчанию) смотрит на TTY.
  При `LOG_FILE` добавляется файл с ротацией, всегда JSON.
- Записи сторонних библиотек (SQLAlchemy, uvicorn, aiohttp, alembic)
  проходят через ту же цепочку процессоров: мост
  `structlog.stdlib.ProcessorFormatter` стоит на единственном обработчике
  root. Уровень root — `WARNING`, логгеры приложения получают `LOGGING`,
  точечные исключения задаёт `LOG_LEVELS`
  (`sqlalchemy.engine=INFO,aiohttp=DEBUG`).
- Секреты снимает процессор `mask_secrets`: по имени поля (`token`,
  `password`, `secret`, `api_key`, `authorization`, `credential` —
  только у строковых значений) и по значению в query-строках
  (`?token=…`). Пароль в DSN маскируется отдельно, хост и база остаются.
  Локальные переменные в трейсбеках не выгружаются.
- Контекст (`structlog.contextvars`) привязывается в `Dispatcher.trigger`
  (`trace_id`, `event_id`, `event_type`, `chat_id`, `user_id`), в
  `run_handler` (`handler`) и в `RequestContextMiddleware`
  (`request_id`, `method`, `path`; `user_id` добавляет `get_current_user`).
  **Порядок важен:** хэндлеры стартуют в `TaskGroup`, и каждая задача
  получает копию контекста в момент `create_task` — общие поля надо
  привязать до создания задач, а имя хэндлера уже внутри задачи.
- Access-лог uvicorn выключен (`access_log=False`): свою строку
  `http.request` со `status` и `duration_ms` пишет middleware.
- В тестах `init_logging` подменён, а structlog настраивается фикстурой
  `_configure_structlog` в `tests/conftest.py` — иначе вывод шёл бы мимо
  stdlib и `caplog` ничего не видел бы.

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
(монорепозиторий). PostgreSQL на 16432→5432. Фронтенд собирается в статику
через `pnpm build`.
