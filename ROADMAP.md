# ROADMAP

План развития vkt-bot. Составлен 2026-09-09 после сверки кода с актуальной
спецификацией VK Teams Bot API (`https://teams.vk.com/botapi/api.yaml`).

Порядок фаз жёсткий: тесты → threads → актуализация клиента → панель.
Внутри фазы задачи отсортированы по критичности.

Связанные документы: [TODO.md](TODO.md) — продуктовые идеи, [IDEAS.md](IDEAS.md).

---

## Фаза 1. Тесты на весь работающий код — ✅ сделано

Цель — зафиксировать текущее поведение до того, как начнём его менять. Всё
последующее (threads, фиксы клиента, панель) опирается на эту сетку.

**Итог:** 850 тестов, покрытие 97% (порог в CI — 70%). Набор гоняется и на
SQLite (по умолчанию, без внешних сервисов), и на PostgreSQL (`TEST_DB_URL`,
так делает CI). Как запускать — в [CLAUDE.md](CLAUDE.md#testing).

### 1.0 Инфраструктура (блокеры, делать первыми) — ✅

Было: код физически нетестируем — проблемы на уровне импортов.

Сделано:

- `config.py` — `get_settings()` с `lru_cache`, `sys.exit` убран, модульный
  `settings` резолвится лениво через `__getattr__`; точка выхода —
  `main.check_settings()`.
- `vkt_bot/__init__.py` и `utils/log.py` больше не читают настройки на
  импорте — иначе `import vkt_bot` всё равно требовал бы полного `.env`.
- `db/session.py` — `create_session_factory(url)` + ленивая
  `LazySessionFactory`; `async_session.configure(...)` подменяет базу сразу
  для всех модулей, которые импортировали её по имени.
- `migrations/env.py` — DSN можно переопределить через `ALEMBIC_DB_URL`.
- Dev-зависимости: `pytest-asyncio`, `pytest-cov`, `aioresponses`, `aiosqlite`.
- `[tool.pytest.ini_options]` и `[tool.coverage.*]` в `pyproject.toml`.
- `tests/` с `conftest.py`, `factories.py`, фикстурами событий и разделами
  `client/`, `dispatcher/`, `db/`, `webapp/`, `handlers/`, `plugins/`,
  `core/`, `utils/`.
- CI: `.github/workflows/test.yml` с service-контейнером PostgreSQL.

Осталось руками: включить job `test` в обязательные проверки для merge в
`master` (настройка branch protection в GitHub).

<details>
<summary>Исходный план 1.0</summary>

Сейчас код физически нетестируем — три проблемы на уровне импортов:

- `src/vkt_bot/config.py:43` — `settings = VktSettings()` в `try/except` с
  `sys.exit(1)`. Любой импорт `vkt_bot.*` без полного `.env` завершает процесс
  pytest. Вынести в `get_settings()` с `functools.lru_cache`, убрать `sys.exit`
  (пусть падает `ValidationError`), точку выхода оставить в `main.py`.
- `src/vkt_bot/db/session.py` — `engine` и `async_session` создаются на уровне
  модуля из `settings.db_url`. Обернуть в фабрику `create_session_factory(url)`,
  чтобы тесты подсовывали свой DSN.
- `src/vkt_bot/app.py` — глобальные `bot` и `dispatcher` на импорте. Оставить
  как есть, но убедиться, что хендлеры принимают `bot`/`dispatcher` аргументом
  (в `HandlerBase.handle` так и есть) и глобали в тестах не нужны.

Дальше:

- Dev-зависимости: `pytest-asyncio`, `pytest-cov`, `aioresponses` (мок для
  `aiohttp.ClientSession`), `pytest-postgresql` **или** `testcontainers[postgresql]`
  (в CI дешевле поднять `services: postgres`), `polyfactory` для фабрик моделей.
- `[tool.pytest.ini_options]` в `pyproject.toml`: `asyncio_mode = "auto"`,
  `testpaths = ["tests"]`, `addopts` с `--cov`.
- Структура `tests/`: `conftest.py` (env, движок, сессия с rollback на каждый
  тест, фейковый `VKTeams`), `tests/fixtures/events/*.json`, разделы
  `client/`, `dispatcher/`, `db/`, `webapp/`, `handlers/`, `plugins/`.
- CI: добавить job `test` (сейчас в `.github/workflows/lint.yml` только ruff).
  Postgres как service-контейнер, `uv sync --all-packages`, `uv run pytest`.
  Сделать обязательным для merge в `master`.

Фикстуры событий брать прямо из спеки: в `schemas.json` у каждого поля есть
`example`, из них собирается валидный payload для всех типов событий.

</details>

### 1.1 `packages/vkteams-client` — ✅

Самый ценный слой для тестов — вся сериализация и парсинг API.

- Парсинг `events/get`: все 9 типов событий, дискриминатор `type` → правильный
  класс, `NewMessagePayload.sender` через `alias="from"`, `timestamp` → datetime.
- `send_text`: сборка query (`replyMsgId`, `forwardChatId`+`forwardMsgId` только
  парой, `parseMode`, `inlineKeyboardMarkup`), таймаут 30 с.
- `send_file`: обе ветки — GET по `fileId` и POST multipart; `ValueError`, если
  не передан ни `file`, ни `file_id`; `FormData(quote_fields=False)`;
  `json.dumps` для списков.
- `send_file_from_url`: имя файла из `Content-Disposition`, из хвоста URL,
  fallback `"file"`; `ValueError` на неуспешный ответ.
- `answer_callback_query`: `show_alert=True` → строка `"true"`.
- `edit_text`, `delete_messages`, `get_members`, `get_self`.
- Негативные кейсы: невалидный JSON, `{"ok": false}`, HTTP 4xx/5xx.

### 1.2 `packages/vkt-dispatcher` — ✅

- `Filter`: композиция `&` / `|` / `~`, `AllFilter`, `AnyFilter`.
- Часть фильтров сейчас **падает с `AttributeError`** (обращение к `event.data`,
  которого у pydantic-модели нет — `filters.py:175` и далее). Написать тесты на
  ожидаемое поведение и пометить `xfail(strict=True)`; в фазе 3.1 они станут
  зелёными. Затронуты: `file`, `image`, `video`, `audio`, `sticker`, `mention`,
  `forward`, `reply`, `url`, `callback_data`, `callback_data_regexp` и
  производные `text`, `media`, `data`.
- `CommandFilter`: префиксы `/`, `.`, `!`; пустой `text`.
- `CommandHandler.check`: регистронезависимость, команда с аргументами,
  пустой `commands`.
- `DefaultHandler`: срабатывает только когда не подошёл никто другой, кидает
  `StopDispatchingError`.
- `Dispatcher.trigger`: параллельный запуск через `TaskGroup`, исключение в
  одном хендлере не роняет остальные (`run_handler` логирует и глушит).
- `apply_middlewares` — все четыре ветки (`async def`, `def`, генератор,
  асинхронный генератор) и порядок post-триггеров в reverse.
- `start_polling`: `last_event_id = max(...)`.

### 1.3 Слой БД — ✅

- `db/repository.py` — `AsyncRepository`: create / get / update / delete / list,
  автовывод генериков.
- `db/query.py` — протокол `Query`, композиция `repository.query(Q1(), Q2())`.
- Конкретные репозитории: `user`, `role`, `chat`, `webhook`, `bot_settings`,
  `log_entry`, `login_token`, `login_history`.
- `db/exceptions.py`, поведение при нарушении констрейнтов, rollback.
- Прогон `alembic upgrade head` на чистой БД как smoke-тест миграций.

### 1.4 `webapp` (httpx + ASGITransport) — ✅

- `auth`: логин (успех / неверный пароль / неактивный пользователь), срок
  жизни JWT, `CurrentUser` и `CurrentAdminUser` (403 обычному пользователю).
- CRUD по всем роутерам: `chats`, `roles`, `chat_users`, `bot_settings`,
  `logs`, `webhooks`.
- `webhooks.public_router` — входящий вебхук: проверка ключа, невалидный
  payload, идемпотентность.
- Валидация схем: 422 на мусор, 404 на отсутствующие id.
- Проверка, что `openapi.json` в репозитории не разошёлся с приложением
  (`uv run export_schema` + `git diff --exit-code`).

### 1.5 Хендлеры бота и плагин — ✅

- `core/handlers/`: `auth`, `chats`, `help`, `roles`, `webhooks`, `callback`,
  `mixins` — на фейковом `VKTeams` (spy), проверяем какие вызовы API сделаны.
- `core/audit.py`, `core/security.py` (хеширование, JWT).
- `plugins/vkt_gitlab`: разбор payload пайплайна, формирование текста и
  клавиатуры, экранирование для `parse_mode="MarkdownV2"` (`api.py:258`).
- `utils/formatters.py`, `utils/message.py`, `utils/datetime.py` — чистые
  функции, самое дешёвое покрытие, брать в первую очередь.

### Готовность фазы

Зелёный `pytest` в CI, покрытие ≥70% по `packages/` и
`src/vkt_bot/{db,core,webapp}`, тесты обязательны для merge.

**Статус:** покрытие 97%, `pytest` зелёный на обоих диалектах. Осталось
включить job `test` в обязательные проверки ветки `master`.

### Что нашли по пути

Тесты фиксируют текущее поведение, поэтому сломанные места помечены
`xfail(strict=True)` или задокументированы в докстрингах. Кандидаты в
фазу 3:

1. **`webapp/api/roles.py`** зовёт `AuditLogger.log_create/log_update/log_delete`
   с аргументом `web_user=`, которого в сигнатуре нет (`user=`). Создание,
   переименование и удаление роли через панель отдают 500. Три `xfail`.
2. **`/togglewebhook`** и `PUT /api/webhooks/{id}` с частичным телом падают:
   `AsyncRepository.update` пишет весь `model_dump()`, поэтому незаданные
   поля затираются в `NULL`, а `webhooks.name`/`is_active` — `NOT NULL`.
   Нужен `model_dump(exclude_unset=True)`.
3. **`DELETE /api/webhooks/{id}`** отвечает 204, но не коммитит: вызов
   `repo.delete(webhook_id)` без `commit=True`.
4. **`GET /api/logs/{id}`** не превращает `NotFoundError` в 404 — уходит 500.
5. **`QueryResult.paginate`** считает `total` по всей таблице: берёт
   `statement.froms[0]` и теряет `where`. Плюс `Select.froms` объявлен
   устаревшим — нужен `get_final_froms()`.
6. **`utils/datetime.now()`** вызывает `datetime.datetime()` без аргументов —
   всегда `TypeError`. Функция нигде не используется.
7. **Наивные `datetime`-колонки.** `LoginToken.expires_at` без таймзоны, а
   `webapp/api/auth.py` делает `expires_at.replace(tzinfo=utc)`. Если
   TimeZone базы не UTC, срок жизни токена уезжает на её смещение.
8. **Строки вместо `UUID`.** `RoleByIdQuery.role_id` и аргумент
   `/glwebhookdel` типизированы как `str`, хотя колонки — `UUID`. PostgreSQL
   приводит сам, любая другая база — нет.
9. **`SenderFilter`** сравнивает `chatId`, а не `userId` отправителя: в личке
   совпадает, в группе фильтр молча не работает.
10. **`CommandHandler()`** без `command` падает с `AttributeError`: `check`
    читает `self.commands`, который `__init__` не задаёт. Ветка
    `not self.commands` недостижима.
11. **Ручки `/gl/webhooks`** (кроме `trigger` и `DELETE`) обращаются к
    несуществующим полям: `Chat.title`, `ChatUser.name`,
    `GlWebhook.created_at`/`updated_at`, `current_user.chat_user_id`.
    См. 3.10.
12. **`uv run shell`** вызывал `setup()` без обязательного аргумента `app` —
    поправлено вместе с точками входа.
13. **Разметка GitLab-уведомлений** уходит с `parse_mode="MarkdownV2"` без
    экранирования: спецсимволы в ветке или сообщении коммита ломают
    сообщение.
14. **`send_text`/`edit_text`** не проверяют `ok` в ответе — неудачная
    отправка проходит незамеченной.

---

## Фаза 2. Обсуждения (threads)

Новая группа методов в API, у нас не реализована вообще.

### 2.0 Research (запускать параллельно с фазой 1)

В спеке нет ни отдельных типов событий для тредов, ни поля `threadId` в
`newMessage`. По FAQ отправка в тред — это обычный `sendText` с `chatId`
равным идентификатору треда (формат `2601@chat.agent`).

Нужен прогон на живом стенде: включить `autosubscribe`, написать в тред и
посмотреть сырой payload `events/get` — как отличить событие из треда от
события родительского чата. От ответа зависит дизайн 2.2. Сырые события уже
логируются (`events_logger` в `client.py:184`).

### 2.1 Клиент

Методы:

| Метод | Подпись |
|---|---|
| `POST /threads/add` | `threads_add(chat_id, msg_id) -> ThreadAddResponse` |
| `GET /threads/autosubscribe` | `threads_autosubscribe(chat_id, enable, with_existing=None) -> Response` |
| `GET /threads/subscribers/get` | `threads_subscribers_get(thread_id, page_size=None, cursor=None) -> ThreadSubscribersResponse` |

Типы в `types.py`: `ThreadAddResponse{ok, threadId}`,
`ThreadSubscribersResponse{ok, cursor, subscribers}`,
`Subscriber{sn, userState}`, `UserState{lastseen}`.

Плюс хелпер `iter_thread_subscribers()` — асинхронный итератор с
автопагинацией по `cursor` (обязателен хотя бы один из `pageSize`/`cursor`).

В докстринге `send_text` явно написать, что для отправки в тред передаётся
`chat_id=thread_id` — иначе будут искать отдельный метод.

### 2.2 Диспетчер

- `ThreadFilter` / `Filter.thread`, `Filter.in_thread(thread_id)` — по итогам 2.0.
- Хелпер «ответить в тред»: создать тред к сообщению и отправить туда текст
  одним вызовом.

### 2.3 Хранение и логика

- Модель `Thread` (`thread_id`, `parent_chat_id`, `root_msg_id`, `created_at`,
  связь с сущностью-источником) + миграция — нужна, чтобы связывать тред с
  тем, из-за чего он создан (пайплайн, MR, задача).
- Автоподписка на треды при добавлении бота в чат
  (`NewChatMembersHandler`), управляемая флагом в `BotSettings`.

### 2.4 Продуктовые сценарии

- Команда `/thread` — создать обсуждение к сообщению-реплаю.
- **Главный кейс:** уведомления GitLab в тред вместо флуда в канал. Один тред
  на пайплайн/MR — обсуждение и статусы в одном месте.

### 2.5 Тесты и документация

Тесты на всё выше (инфраструктура из фазы 1 уже есть). Раздел про треды в
`README.md` и `CLAUDE.md`.

---

## Фаза 3. Актуализация клиента и фиксы

30 эндпоинтов в спеке, реализовано 8. Плюс накопились расхождения.

### 3.1 Баг: `parts` и сломанные фильтры (критично)

`NewMessagePayload` вообще не содержит поля `parts`, поэтому вложения,
упоминания, форварды и реплаи молча выбрасываются при парсинге. А 11 фильтров
обращаются к несуществующему `event.data` и падают с `AttributeError`.

- Добавить `parts: list[MessagePart]` — union `StickerPart | MentionPart |
  VoicePart | FilePart | ForwardPart | ReplyPart` с дискриминатором `type`.
- Переписать фильтры в `packages/vkt-dispatcher/src/vkt_dispatcher/filters.py`
  с `event.data[...]` на работу с моделями.
- `xfail`-тесты из 1.2 снять.

Сейчас баг латентный: в `src/` и `plugins/` эти фильтры не используются. Но
первое же использование упадёт.

### 3.2 Форматирование текста

Изменение API от 11.05.2021, у нас реализовано частично — `format`
передаётся только в `send_file`, хотя по спеке он есть у `sendText`,
`editText` и `events/get`.

- Добавить `format` в `send_text` и `edit_text`.
- Типизированная модель `TextFormat`: `bold`, `italic`, `underline`,
  `strikethrough`, `link{offset,length,url}`, `mention`, `inline_code`,
  `pre{offset,length,code}`, `ordered_list`, `unordered_list`, `quote`.
  Ключи уже совпадают с `StyleType` в `enums.py`.
- `FormatPart` дополнить полями `url` (для `link`) и `code` (для `pre`) —
  сейчас там только `offset` и `length`.

### 3.3 Возвращаемые значения

`send_text` и `edit_text` объявлены как `-> None`, хотя `sendText` отдаёт
`{ok, msgId}`. Без `msgId` нельзя потом отредактировать или удалить своё
сообщение — практическая дырка. Вернуть `MsgResponse`.

### 3.4 Inline-клавиатуры

- `inlineKeyboardMarkup` в `send_text`/`edit_text` передаётся как есть, без
  `json.dumps` (в `send_file` — с `dumps`). Привести к одному виду.
- Типизированные модели вместо `Any`: `UrlButton{text, url, style}`,
  `CallbackButton{text, callbackData, style}`,
  `style: Literal["attention", "primary", "base"]` (дефолт `base`),
  `InlineKeyboardMarkup` как `list[list[Button]]` + билдер.

### 3.5 Полные payload'ы событий

Сейчас `payload: Any` у трёх событий, хотя спека их полностью описывает:

- `DeletedMessagePayload` — `msgId`, `chat`, `timestamp`;
- `PinnedMessagePayload` — `chat`, `from`, `msgId`, `text`, `format`, `timestamp`;
- `UnpinnedMessagePayload` — `chat`, `msgId`, `timestamp`.

Плюс: `chat` в `CallbackQueryEventPayload` (в спеке есть, у нас нет),
`about` и `photo` в `GetSelfResponse`.

Сделано: `LeftChatMembersPayload` и `ChangedChatInfoPayload` — потребовались
для учёта состава чатов. `changedChatInfo` в документации отсутствует,
поля восстановлены по реальным ответам и помечены комментарием.

### 3.6 Пагинация и мелочи

- `cursor` в `get_members` и в `GetMembersResponse` — на больших чатах список
  сейчас обрезается.
- `delete_messages` — принимать `list[str]`, API поддерживает массив `msgId`.

### 3.7 Недостающие эндпоинты

По убыванию ценности:

1. `files/getInfo` → `{type, size, filename, url}` — без него нельзя скачать
   вложение по `fileId`. Нужен для любой работы с файлами от пользователей.
2. `chats/getInfo` — `oneOf` private / group / channel. У private есть `nick`,
   `about`, `isBot`, `language`; у group и channel — `title`, `about`, `rules`,
   `inviteLink`, `public`, `joinModeration`.
3. `chats/getAdmins`.
4. `chats/sendActions` (`typing` / `looking`) — заметно улучшает UX долгих
   операций. Звать каждые 10 секунд, пока действие активно.
5. `messages/sendVoice` — GET по `fileId` и POST multipart, форматы aac/ogg/m4a.
6. Модерация: `chats/blockUser` (+`delLastMessages`), `chats/unblockUser`,
   `chats/getBlockedUsers`, `chats/getPendingUsers`, `chats/resolvePending`
   (`approve` + либо `userId`, либо `everyone` — не одновременно),
   `chats/members/delete`.
7. Управление чатом: `chats/setTitle`, `chats/setAbout`, `chats/setRules`,
   `chats/avatar/set` (POST multipart, отдельный ответ
   `{ok: false, description: "Image is porn"}`), `chats/pinMessage`,
   `chats/unpinMessage`.
8. Только on-premise (`im_tags: myteam_only`, требуют внесения бота в таблицу
   `bot_api_private_methods`, спрятать за фича-флагом): `chats/createChat`
   (→ `{sn}`), `chats/members/add` — может вернуть частичный успех
   `{ok, failures: [{id, error}]}` с кодами `user_waiting_for_approve`,
   `user_must_join_by_link`, `user_blocked_confirmation_required`,
   `user_must_be_added_by_admin`, `user_already_added`,
   `bot_setjoingroups_false`, `user_captcha`.

### 3.8 Устойчивость

- **Рейт-лимиты.** По FAQ: 30 сообщений/сек в личные диалоги, 1 сообщение/сек
  в отдельный чат, при превышении — ошибка `ratelimit`. Ни троттлинга, ни
  бэкоффа сейчас нет. Добавить per-chat лимитер и retry с экспоненциальным
  бэкоффом на `ratelimit` и 5xx.
- **Лимит querystring.** 60 КБ на query, 50 МБ на тело. `send_text` кладёт
  текст в query — на длинных сообщениях упрёмся. Добавить проверку длины и
  разбивку на части.

### 3.9 Уборка

- Выпилить легаси-энумы `ImageType`, `VideoType`, `AudioType` в
  `enums.py` (односимвольные коды `"0"`, `"8"`, `"G"` — в текущей спеке не
  встречаются). Актуальный `PayLoadFileType` совпадает с `fileInfo.type`.
- Закомментированный код: `handlers.py` (`FeedbackCommandHandler`,
  `UnknownCommandHandler`), `dispatcher.py` (`lyfecycle`).
- Опечатка в имени: `lyfecycle_hooks` → `lifecycle_hooks`.

### 3.10 Расхождения репозитория с документацией

- `src/vkt_bot/scripts/create_admin.py` **не существует**, хотя
  `make createsuperuser` и CLAUDE.md на него ссылаются. Написать (нужен для
  4.1) или убрать из документации.
- `src/vkt_bot/webapp/api/users.py` описан в CLAUDE.md, но отсутствует.
  См. 4.1.
- В корне репозитория лежат артефакты: `collapsible-example.vue`, `tmp/`,
  `api.yaml`. Разобрать.
- ~~`CLAUDE.md` пишет «Test framework not currently configured»~~ — обновлено
  в фазе 1.

---

## Фаза 4. Панель управления

Есть: Login, Dashboard, Chats, Roles, ChatUsers (+detail), GitLabWebhooks,
BotSettings, Logs, Webhooks. Стек: Vue 3 + Pinia + TanStack Query +
Tailwind v4 + shadcn-vue, клиент API генерируется Hey API.

### 4.1 Управление пользователями панели (критично)

API `webapp/api/users.py` не реализован — то есть создать, отключить или
сменить пароль пользователю панели нельзя ничем, кроме прямого SQL. А первый
админ создаётся скриптом, которого нет (см. 3.10).

- `scripts/create_admin.py`.
- `webapp/api/users.py`: CRUD, смена пароля, `is_active`, `is_superuser`.
- Экран Users + смена собственного пароля в профиле.

### 4.2 Экран обсуждений

После фазы 2: список тредов, переключатель автоподписки по чатам, просмотр
подписчиков, отправка сообщения в тред.

### 4.3 Управление чатами из панели

После 3.7: переименование, описание, правила, аватар, закрепить и открепить
сообщение, участники (добавить / удалить / забанить / разбанить), очередь на
вступление, список админов.

### 4.4 Компоновщик сообщений

Отправка от лица бота: текст с `format`/`parseMode`, визуальный конструктор
inline-клавиатуры с превью и стилями кнопок, отправка файла и голосового,
выбор чата или треда как получателя.

### 4.5 Осмысленный дашборд

Сейчас на `DashboardView` демо-компоненты из shadcn-блока (`SectionCards`,
`ChartAreaInteractive`, `DraggableRow`, `NavDocuments`) с заглушками.
Заменить на реальные метрики: события и сообщения по времени (данные есть в
`LogEntry`), топ активных чатов, ошибки, состояние поллинга и `lastEventId`,
версия бота. Потребуются агрегирующие эндпоинты в `webapp/api/`.

### 4.6 UX и уборка

- По пожеланию из `CLAUDE.md` — реже использовать компонент `Card`.
- Удалить неиспользуемое: `stores/counter.ts`, `collapsible-example.vue` из
  корня репозитория, демо-компоненты дашборда.
- Единый плотный layout таблиц, консистентные пустые состояния и скелетоны.

### 4.7 Тесты фронтенда

Сейчас ни одного теста и ни одной тестовой зависимости.

- Vitest + `@vue/test-utils` — сторы, composables, критичные компоненты.
- Playwright — 3–4 сквозных сценария: логин, CRUD роли, отправка сообщения,
  создание вебхука.
- Добавить в CI: `pnpm type-check`, `pnpm lint`, `pnpm test`.

### 4.8 Автоматизация клиента API

`make generate_client` есть, но в CI не проверяется. Добавить job, который
регенерирует клиент и падает, если `git diff` не пуст — иначе фронт будет
тихо расходиться с бэкендом.

---

## Что можно делать параллельно

- **2.0 (research по тредам)** не зависит от фазы 1 — нужен только доступ к
  стенду. Запускать сразу, результат нужен к 2.2.
- **3.9 и 3.10 (уборка и расхождения с документацией)** — независимые мелкие
  задачи, годятся для заполнения пауз.
- **4.7 (тесты фронта)** не зависит от фаз 1–3.
- ~~**1.0 (тестируемость `config.py` и `db/session.py`)**~~ — сделано.
