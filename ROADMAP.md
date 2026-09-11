# ROADMAP

План развития vkt-bot. Составлен 2026-09-09 после сверки кода с актуальной
спецификацией VK Teams Bot API (`https://teams.vk.com/botapi/api.yaml`).

Порядок фаз жёсткий: тесты → threads → актуализация клиента → панель.
Внутри фазы задачи отсортированы по критичности. Фаза 5 (архитектура и
техдолг) идёт поперёк остальных: её первые пункты — дефекты, а не улучшения.

Связанные документы: [TODO.md](TODO.md) — продуктовые идеи, [IDEAS.md](IDEAS.md),
[EVENTS.md](EVENTS.md) — план по событиям и логированию (structlog).

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
- Фильтры по `parts` (`file`, `image`, `video`, `audio`, `sticker`, `voice`,
  `mention`, `forward`, `reply`, `url`, `callback_data`,
  `callback_data_regexp` и производные `text`, `media`, `data`) до 3.1
  падали с `AttributeError`: читали `event.data`, которого у pydantic-модели
  нет. Тесты были написаны на ожидаемое поведение и помечены
  `xfail(strict=True)`; после 3.1 сняты и зелёные.
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

## Фаза 2. Обсуждения (threads) — частично сделано

Новая группа методов в API. Клиент и автоподписка готовы, продуктовые
сценарии (тред на пайплайн/MR) — нет.

### 2.0 Research — ✅

По документации тред — это чат со своим `chatId` (`2601@chat.agent`):
отдельных типов событий у обсуждений нет, сообщение из треда приходит
обычным `newMessage`, отправка в тред — `sendText` с `chatId` треда.
События доходят только подписчикам, подписка — `threads/autosubscribe`.

Проверено на живом стенде 2026-09-09:

- события из треда приходят обычным `newMessage` с `chatId` треда, `type`
  разбирается штатно, `title` у треда пустой;
- `messages/sendText` в тред работает, включая упоминания `@[user_id]`;
- `threads/add`, `threads/autosubscribe`, `threads/subscribers/get` работают;
- **пересылка из треда не поддерживается**: `forwardChatId` = id треда →
  `Bad request` (в личку, в родительский чат и в сам тред, в чужом и в
  своём треде, при любом формате `msgId`); `forwardChatId` родителя с
  `msgId` из треда → `msgId not found`; из обычного чата пересылка идёт;
- `replyMsgId` внутри треда → `Bad request`;
- `chats/getInfo` и `chats/getMembers` для треда недоступны
  (`Bad request` / `Permission denied`).

Проверено на живом стенде 2026-09-10:

- **`threads/add` — get-or-create**: три вызова на одном `(chatId, msgId)`
  вернули один и тот же `threadId`, без ошибки и без дублей. Это
  единственный способ узнать id уже существующего обсуждения — в событиях
  ссылки на тред нет, `threads/get` в спеке не существует. Цена — вызов не
  только читает: у сообщения без обсуждения он его создаст;
- id треда неотличим от id обычной группы (`693938330@chat.agent` при
  родителе `694348323@chat.agent`), пример `2601@chat.agent` из
  документации сбивает с толку;
- внутри треда `threads/add` → `Bad request`: вложенных обсуждений нет;
- `threads/subscribers/get` с id обычного чата → `Incorrect threadId`.

Отсюда дизайн 2.2: отличить событие из треда от события чата ни по самому
событию, ни по виду `chatId` нельзя — только вызовом
`threads/subscribers/get`.

### 2.1 Клиент — ✅

| Метод | Подпись |
|---|---|
| `GET /threads/add` | `threads_add(chat_id, msg_id) -> ThreadAddResponse` |
| `GET /threads/autosubscribe` | `threads_autosubscribe(chat_id, enable, with_existing=None) -> Response` |
| `GET /threads/subscribers/get` | `threads_subscribers_get(thread_id, page_size=None, cursor=None) -> ThreadSubscribersResponse` |

Плюс `iter_thread_subscribers()` — асинхронный итератор с автопагинацией по
`cursor`, и типы `ThreadAddResponse`, `ThreadSubscribersResponse`,
`Subscriber`, `UserState`. Булевы query-параметры сериализуются вручную:
`aiohttp` не умеет `bool`. В докстринге `send_text` написано, что в тред
пишут через `chat_id=thread_id`, в докстринге `threads_add` — что метод
работает как get-or-create. Обёртка `core.threads.get_or_create_thread()`
прячет эту семантику и не поднимает ошибок наружу.

### 2.2 Диспетчер — закрыто как ненужное

`ThreadFilter` / `Filter.thread` делать не надо: событие из треда ничем не
отличается от события чата (см. 2.0), а единственная проверка стоит запроса
к API — фильтр, который дёргается на каждое событие, ходить в сеть не
должен. Проверять «это тред?» стоит только там, где от ответа что-то
зависит, как в `NotifyRoleIsTaggedHandler.thread_subscribers`.

Хелпер «получить тред к сообщению» — ✅ `core.threads.get_or_create_thread`.

### 2.3 Хранение и логика — частично

- ✅ Автоподписка на треды при добавлении бота в чат
  (`ChatMembersJoinedHandler` → `core/threads.py`), с `withExisting=true`.
  Глобальный флаг — настройка `threads_autosubscribe` в `bot_settings`,
  по чату — команда `/subscribethreads [off]` (админ).
- ✅ Призыв по роли работает в обсуждениях: обработчик ловит любой
  `newMessage`, пересылка идёт из `chatId` треда, название чата берётся из
  события или из таблицы `chats`. Пересылка из треда API запрещена, поэтому
  уведомление уходит текстом (автор + текст сообщения) — решение
  подтверждено владельцем 2026-09-09.
- ~~Модель `Thread` (`thread_id`, `parent_chat_id`, `root_msg_id`,
  `created_at`, связь с сущностью-источником) + миграция.~~ **Не нужна:**
  `threads/add` идемпотентен (2.0), то есть `threadId` — не состояние, а
  производная от `(chat_id, msg_id)`, которую API отдаёт по запросу.
  Хранить надо не тред, а якорь — `msgId` сообщения, к которому он
  привязан. Заодно снимается гонка: два одновременных вызова получат один
  и тот же тред.

### 2.4 Продуктовые сценарии

- Команда `/thread` — создать обсуждение к сообщению-реплаю. Состояние не
  нужно: повторный вызов на том же сообщении вернёт тот же тред.
- **Главный кейс:** уведомления GitLab в тред вместо флуда в канал. Один тред
  на пайплайн/MR — обсуждение и статусы в одном месте. Нужен ровно один
  маппинг «пайплайн/MR → `msgId` первого уведомления»: сейчас
  `vkt_gitlab/api.py` отправляет сообщение и забывает про него, `msgId` не
  сохраняется нигде, а `GlWebhook` знает только `chat_id`. Дальше каждый
  следующий статус — `get_or_create_thread(chat_id, anchor_msg_id)` и
  `send_text` в полученный `threadId`.

### 2.5 Тесты и документация

- ✅ Тесты: клиент (`tests/client/test_threads.py`), хелперы
  (`tests/core/test_threads.py`), автоподписка при
  добавлении бота, команда `/subscribethreads`, призыв по роли из треда,
  булевы настройки. Фикстура события из треда —
  `tests/fixtures/events/new_message_in_thread.json`.
- ✅ Раздел про треды в `CLAUDE.md`.
- Осталось: `README.md` — после 2.4.

---

## Фаза 3. Актуализация клиента и фиксы

30 эндпоинтов в спеке, реализовано 11. Плюс накопились расхождения.

### 3.1 Баг: `parts` и сломанные фильтры — ✅

Сделано 2026-09-10. Формы частей взяты из `schemas.json` первоисточника, а
не восстановлены по памяти.

- `parts: list[MessagePart]` в `NewMessagePayload` — дискриминированное
  объединение `StickerPart | VoicePart | FilePart | MentionPart |
  ForwardPart | ReplyPart` плюс `UnknownPart` про запас: новый тип части
  не должен ронять разбор всего события, иначе бот молчал бы вместо того,
  чтобы ответить на остальное.
- Фильтры переписаны на модель, `event.data` больше нигде нет. Появился
  `VoiceFilter` — часть в спеке была, фильтра не было.
- `CallbackDataRegexpFilter` возвращал объект совпадения вместо булева —
  починено заодно.
- Все 17 строгих `xfail` из 1.2 сняты и зелёные.

Польза, ради которой это чинилось: у упоминания появился точный `userId`
(в разметке `format.mention` его нет), а в истории сообщений на месте
вложения теперь `[изображение: Схема]` и текст пересланного сообщения
вместо безликого `[вложение]`.

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

### 3.3 Возвращаемые значения — ✅

`send_text` и `edit_text` возвращают `MsgResponse` (`msgId` необязателен —
при `ok: false` его нет), у `Response` появилось поле `description`. Отказ
сервера логируется как ERROR: раньше `ok` не проверялся, и несостоявшаяся
отправка выглядела в логах успешной.

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
- **Падение polling.** `Dispatcher.start_polling` не ловит сетевые ошибки:
  `TimeoutError` от long-poll завершает процесс бота (наблюдалось
  2026-09-09). Нужен retry с бэкоффом вокруг `get_events`.
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
- Отладочные `print`: `webapp/app.py` (в фабрике приложения) и
  `plugins/vkt_gitlab/__init__.py` (`"gl is installed"`).
- `Dispatcher.__init__` заводит `self.message_handlers = []` — поле не
  объявлено в классе и нигде не читается; `Dispatcher.base_url` дублирует
  клиентский и тоже не используется.
- `CommandHandler.check` читает `self.commands`, которое `__init__` создаёт
  только при переданном `command`: подкласс без `ClassVar` даст
  `AttributeError`. Задать пустой список по умолчанию.

### 3.10 Расхождения репозитория с документацией

- `src/vkt_bot/scripts/create_admin.py` **не существует**, хотя
  `make createsuperuser` и CLAUDE.md на него ссылаются. Написать (нужен для
  4.1) или убрать из документации.
- `src/vkt_bot/webapp/api/users.py` описан в CLAUDE.md, но отсутствует.
  См. 4.1.
- В корне репозитория лежат артефакты: `collapsible-example.vue`, `tmp/`,
  `api.yaml`. Разобрать. Плюс `node_modules/` в корне не попал в
  `.gitignore` и висит в `git status`.
- Восемь md-документов в корне (`TODO`, `IDEAS`, `CHANGES`, `ROADMAP`,
  `EVENTS`, `WEBAPP_SUMMARY`, `QUICKSTART_API`, `WEBHOOKS_N8N`) частично
  дублируют друг друга. Свести к `README` + `CLAUDE` + `ROADMAP` + `TODO`,
  остальное — в `docs/` или в историю.
- ~~`CLAUDE.md` пишет «Test framework not currently configured»~~ — обновлено
  в фазе 1.

---

## Фаза 4. Панель управления

Есть: Login, Обзор, Чаты, Участники (+карточка), Роли (+карточка), Вебхуки,
GitLab, Настройки, Журнал действий. Стек: Vue 3 + Pinia + TanStack Query +
Tailwind v4 + shadcn-vue, клиент API генерируется Hey API.

Структура страниц и общие компоненты (`components/layout`, `components/data`)
описаны в `CLAUDE.md`.

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

### 4.5 Осмысленный дашборд — частично сделано

Сделано: `GET /api/overview` (счётчики чатов, участников, ролей и своих
вебхуков + активность по дням из `log_entries`), на `DashboardView` — плитки,
столбчатый график активности за 14 дней и последние записи журнала. Столбцы, а
не линия: суточные счётчики дискретны, интерполяция рисовала бы события,
которых не было.

Осталось: топ активных чатов, ошибки, состояние поллинга и `lastEventId`,
версия бота — для них нужны новые агрегаты и данные, которых бот сейчас не
хранит.

### 4.6 UX и уборка — ✅ сделано

- `Card` из страниц ушла совсем: разделы группирует `PageSection` с
  правилом-разделителем, таблицы — рамка `DataTableShell`.
- Удалены демо-компоненты дашборда (`SectionCards`, `ChartAreaInteractive`,
  `DataTable`, `DraggableRow`, `DragHandle`, `NavDocuments`, `NavSecondary`,
  `ThemeToggle`), `stores/counter.ts`, лог ошибки Hey API и `.ruff_cache`
  внутри фронта; иконки в коде сведены на `lucide-vue-next` (сам пакет
  `@tabler/icons-vue` из `package.json` не выпилен: локальный `pnpm remove`
  требует миграции стора).
- Единый плотный layout таблиц, пустые состояния и скелетоны — в
  `DataTableShell` / `EmptyState`; пагинация — одна на все списки
  (`TablePagination` вместо пяти копий).
- Починено по пути: имя пользователя в сайдбаре (`/api/auth/me` отдаёт
  `display_name`), тёмная тема на странице входа и в сообщениях настроек,
  ссылка вебхука GitLab (был лишний `/api` и `window.location.origin`),
  `entity_id: "None"` в журнале (аудит писался до `flush`).

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

## Фаза 5. Архитектура и техдолг

Составлено 2026-09-10 по обзору всего кода: `packages/` (клиент, диспетчер),
`src/vkt_bot/` (core, db, webapp), `plugins/vkt-gitlab/`, тесты. На момент
обзора: линт чистый, 1026 тестов зелёные, 17 `xfail` (все — ROADMAP 3.1;
починены там же).

Фаза не блокирует 3 и 4, но 5.1–5.3 стоит сделать раньше любых новых
ручек и хендлеров: это дефекты, а не улучшения.

### Что держится хорошо

Чтобы не переписать заодно и работающее:

- Слой БД честно разделён на `models → repositories → queries`; протокол
  `Query.apply` даёт комбинируемые условия без утечки SQLAlchemy в хендлеры.
- Ленивость (`get_settings()` с `lru_cache`, `LazySessionFactory`,
  единственная точка выхода в `check_settings()`) не декларация — на ней
  держится изоляция тестов через внешнюю транзакцию.
- Нетривиальные решения задокументированы там, где живут: `core/threads.py`
  и `handlers/roles.py` объясняют, *почему* так, а не только что делает код.

### 5.1 Сломанный CRUD плагина GitLab + тайпчекер (критично)

`plugins/vkt_gitlab/src/vkt_gitlab/api.py` обращается к полям, которых у
`ChatUser` нет:

- `current_user.chat_user_id` — в `create_webhook`;
- `webhook.created_by.name` — во всех четырёх сборках `GlWebhookRead`.

У модели есть `id`, `display_name`, `nick`, `first_name`, `last_name`.
Итог: `GET /gl/webhooks`, `POST /gl/webhooks`, `GET /gl/webhooks/{id}` и
`PATCH /gl/webhooks/{id}` отвечают 500. Работают только `trigger` и
`DELETE` — ровно то, что покрыто тестами в `tests/plugins/test_gitlab.py`.

- Починить обращения: `created_by_id=current_user.id`,
  `created_by_name=webhook.created_by.display_name`.
- Дописать тесты на четыре ручки — сейчас на них нет ни одного.
- Завести тайпчекер (`mypy` или `pyright`) и job в CI. Ошибка этого класса
  ловится одним прогоном; CLAUDE.md уже предупреждает, что тайпчекера нет,
  и вот первая цена.

### 5.2 Одна политика транзакций (критично)

Сейчас в одном приложении три разных подхода:

- ручки `webapp/api/roles.py` и `webapp/api/chat_users.py` коммитят сами;
- `webapp/api/webhooks.py` не коммитит нигде — `update` и `delete`
  отрабатывают вхолостую (зафиксировано тестами
  `TestDeleteWebhook::test_returns_204_but_does_not_commit` и
  `TestUpdateWebhook::test_partial_update_is_broken`);
- репозитории умеют коммитить чужую сессию изнутри
  (`create_with_api_key`, `regenerate_api_key`).

Тесты этого не ловят: сессия теста и сессия приложения делят одно
соединение во внешней транзакции, поэтому незакоммиченная запись всё равно
видна.

- Правило: коммитит владелец сессии — зависимость `get_session()` или
  хендлер бота. Репозиторий не коммитит никогда.
- Убрать параметр `commit=` из `AsyncRepository` и вызовов.
- `AsyncRepository.update` — `model_dump(exclude_unset=True)`: сейчас
  опущенные поля затираются в `None`. Это дефект базового класса, а не
  только вебхуков, и выстрелит на любом `PATCH`.
- Снять оба «известных дефекта» из тестов вебхуков.

### 5.3 Middleware вне защиты от ошибок

`Dispatcher.trigger` применяет middleware **вне** `try`: ошибки глушит только `run_handler`. `CreateChatMiddleware` ходит в
БД на каждое сообщение, поэтому сбой БД поднимается в `start_polling`, где
ловятся лишь `TimeoutError | OSError | ClientError`, и роняет процесс.

Это та же проблема, что чинили в 3.8 для сети, только с другой стороны.

- Обернуть `apply_middlewares` в `trigger` так же, как тело `run_handler`.
- Решить явно, что делать с событием, если `on_event` упал: пропускать или
  всё же звать хендлеры.

### 5.4 `core` не должен зависеть от `webapp`

`core/repositories/webhook.py` импортирует схемы из
`vkt_bot.webapp.schemas.webhook`, а `core/handlers/webhooks.py` делает то же
локальными импортами внутри `CreateWebhookHandler.callback` и
`ToggleWebhookHandler.callback` — обход цикла.

У всех остальных репозиториев схемы лежат рядом (`CreateRoleSchema` в
`repositories/role.py`); вебхуки — единственное исключение, и именно оно
разворачивает направление зависимостей.

- Перенести `WebhookCreateSchema` / `WebhookUpdateSchema` в
  `core/repositories/webhook.py`; в `webapp/schemas/webhook.py` оставить
  только то, что описывает HTTP (запросы и ответы ручек).
- Локальные импорты в хендлерах убрать — они станут не нужны.

### 5.5 Цикл «приложение ↔ плагин» и контракт плагина

Корневой `pyproject.toml` объявляет зависимость на `vkt-gitlab`, а плагин
импортирует хост: `vkt_bot.app`, `vkt_bot.webapp.dependencies` и
`vkt_bot.core.security` (всё — в `api.py`). При этом
`plugins/vkt_gitlab/pyproject.toml` объявляет `dependencies = []`.

Entry points дают позднее связывание в рантайме, но статически цикл
настоящий: плагин не собирается и не ставится отдельно, а «автообнаружение»
работает только потому, что плагин всегда установлен. Публичного контракта
для стороннего плагина нет.

- Выделить `vkt_bot.plugin_api` — то, на что плагину разрешено опираться:
  бот, `SessionDep`, `AdminRequiredMixin`, хеши, регистрация роутеров.
- Плагин зависит от `vkt-bot` (или от отдельного пакета с контрактом),
  корень плагин в обязательных зависимостях не держит — ставится extra'ой.
- Дописать в CLAUDE.md, что плагину можно импортировать, а что нет.

### 5.6 `vkt_bot.app`: синглтоны и настройки на импорте

`app.py` — `from vkt_bot.config import settings` срабатывает
module-`__getattr__` в момент импорта, то есть `get_settings()` вызывается
сразу. Ленивость конфига, ради которой написан `__getattr__`, теряется для
девяти модулей приложения и плагина, которые импортируют `vkt_bot.app`.

Плюс один экземпляр `VKTeams` делят процесс бота и веб-процесс, а его
`aiohttp.ClientSession` создаётся лениво и привязывается к тому event loop,
который первым её тронул.

- В `app.py` брать токен не на импорте: либо `get_settings()` внутри
  фабрики, либо ленивый прокси по образцу `LazySessionFactory`.
- Разделить экземпляры бота для polling и для веб-процесса или явно
  задокументировать, что он один и почему это безопасно.

### 5.7 `bootstrap()` отдельно от `create_app()`

`main.start_bot()` собирает FastAPI-приложение, которое боту
не нужно, — только чтобы `setup()` импортировал `core.handlers` и плагины.
То же в `shell()`. Сам `setup(app)` смешивает три несвязанных дела:
логирование, регистрацию моделей, загрузку плагинов.

- `bootstrap()` — логи, Sentry, модели, хендлеры, плагины; зовут оба
  процесса.
- `create_app()` — только сборка веб-приложения; роутеры плагинов
  подключает через результат `bootstrap()`, а не наоборот.

### 5.8 Последовательная обработка событий

`start_polling` идёт по пачке событий с `await self.trigger(event)`:
следующее событие ждёт завершения **всех** хендлеров предыдущего. С учётом
`NotifyRoleIsTaggedHandler.is_thread`, который делает запрос к API на каждое
сообщение любого чата, очередь выстраивается за самым медленным хендлером.

- Разнести события по задачам, сохранив порядок в пределах чата.
- `last_event_id` двигать так, чтобы падение обработки не теряло событие
  (сейчас порядок правильный — учесть при переделке).
- Кэшировать результат `is_thread` по `chatId`: он не меняется.

### 5.9 Мёртвый механизм `StopDispatchingError`

`DefaultHandler.handle` его бросает, а `Dispatcher.run_handler`
ловит `Exception` и пишет «Ошибка при обработке хэндлера». Диспетчеризация
не останавливается, зато в логе появляется ошибка на штатном пути.

Обработать явно в `run_handler` или убрать вместе с `DefaultHandler`.

### 5.10 Дубли: вебхуки, JWT, хеширование

- **Два механизма вебхуков.** `core.Webhook` (`/api/webhooks` + публичный
  `/webhooks/{id}`, bcrypt напрямую) и `vkt_gitlab.GlWebhook`
  (`/gl/webhooks`, passlib). Дублируется CRUD, хранение секрета, привязка к
  чату, проверка прав. GitLab-вариант — частный случай общего: шаблон
  сообщения плюс фильтр по типу события. Свести к одному, GitLab оставить
  как форматтер.
- **Две библиотеки JWT.** `jose` в `webapp/dependencies.py` и
  `webapp/api/auth.py`, `pyjwt` в `core/security.py`. Оставить одну.
- **`core/security.create_access_token` не используется приложением** —
  только тестами; рабочая функция живёт в `webapp/api/auth.py`. Удалить дубль.
- **Два способа хешировать.** `passlib[bcrypt]` в `core/security.py`, голый
  `bcrypt` в `core/repositories/webhook.py`. Выбрать один.

### 5.11 Безопасность веб-слоя

- **CORS.** `allow_origins=["*"]` вместе с `allow_credentials=True`
  (`create_app` в `webapp/app.py`) — по спеке несовместимо: браузер отвергнет
  credentialed-запросы, а для токена в заголовке это просто «открыто всем».
  Список источников вынести в настройки.
- **Публичный `/webhooks/{id}` без ограничений.** `check_rate_limit` всегда
  возвращает `True` (`core/repositories/webhook.py`), `log_webhook_call` —
  пустышка. Ручка рассылает сообщения в чат неограниченно, и каждый вызов
  ещё и считает bcrypt. Связано с 3.8 (рейт-лимиты API): нужен и свой лимит
  на входящие вызовы, и учёт вызовов, раз он уже заявлен в коде.

### Порядок

1. 5.1 — четыре ручки не работают, и ничто об этом не скажет.
2. 5.2 — снимает два зафиксированных дефекта и все будущие того же вида.
3. 5.3 — бот перестанет падать от сбоя БД.
4. 5.4 и 5.7 — расцепляют `core ↔ webapp` и убирают FastAPI из процесса бота.
5. Дальше 5.5, 5.6, 5.10 — по мере необходимости; 5.8 и 5.11 — когда
   появится нагрузка.

---

## Что можно делать параллельно

- **2.0 (research по тредам)** не зависит от фазы 1 — нужен только доступ к
  стенду. Запускать сразу, результат нужен к 2.2.
- **3.9 и 3.10 (уборка и расхождения с документацией)** — независимые мелкие
  задачи, годятся для заполнения пауз.
- **4.7 (тесты фронта)** не зависит от фаз 1–3.
- ~~**1.0 (тестируемость `config.py` и `db/session.py`)**~~ — сделано.
