# Логи

Один поток (stdout), один формат на процесс, структурные поля вместо
подстановок в текст. Локально — читаемая консоль, на сервере — JSON,
который забирает promtail и кладёт в Loki.

Настройка живёт в [`src/vkt_bot/logging_setup.py`](../src/vkt_bot/logging_setup.py).

## Как писать в лог

```python
import structlog

logger = structlog.get_logger("vkt_bot.handlers.roles")

logger.info("role.assigned", role="devs", user_id=user_id)
logger.warning("thread.check_refused", chat_id=chat_id, reason=description)
logger.exception("handler.failed")          # внутри except
```

Правила:

- **Первый аргумент — идентификатор события**, а не предложение:
  `<домен>.<действие>` в `snake_case` (`message.send_failed`,
  `chat.bot_added`). По нему фильтруют в Grafana, поэтому он должен быть
  стабильным: менять формулировку в тексте безобидно, менять
  идентификатор — нет.
- **Всё переменное — в поля.** `chat_id=...`, а не `f"чат {chat_id}"`:
  иначе по чату не сгруппировать.
- **Единый словарь полей:** `chat_id`, `user_id`, `msg_id`, `thread_id`,
  `event_id`, `event_type`, `trace_id`, `request_id`, `webhook_id`,
  `duration_ms`, `status`, `reason`, `handler`.
- Логгер называется по модулю (`vkt_bot.handlers.chats`,
  `vkteams_client.send_message`) — по нему настраиваются уровни.

## Контекст

Поля контекста добавляются ко **всем** строкам внутри одной единицы
работы, включая строки библиотек.

| Где | Что привязывается |
|---|---|
| `Dispatcher.trigger` | `trace_id`, `event_id`, `event_type`, `chat_id`, `user_id` |
| `Dispatcher.run_handler` | `handler` |
| `RequestContextMiddleware` | `request_id`, `method`, `path` |
| `get_current_user` | `user_id` |
| входящий вебхук | `webhook_id`, `chat_id` |

`trace_id` — свой идентификатор обработки события; он же уедет в таблицу
`events` (фаза B плана [EVENTS.md](../EVENTS.md)) и свяжет запись в панели
с логами.

Хэндлеры одного события работают параллельно в `TaskGroup`, и каждая
задача получает **копию** контекста в момент создания. Поэтому общие поля
привязываются до `create_task`, а `handler` — уже внутри задачи. В другом
порядке хэндлеры перетирали бы контекст друг другу.

## Настройки

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `LOGGING` | — (обязательная) | уровень логгеров приложения |
| `LOG_FORMAT` | `auto` | `console`, `json` или `auto` (console при TTY) |
| `LOG_LEVELS` | пусто | точечные уровни: `sqlalchemy.engine=INFO,aiohttp=DEBUG` |
| `ENV` | `local` | поле `env` в каждой строке |
| `SERVICE_NAME` | `vkt-bot` | поле `service`; для веб-сервера задайте своё |
| `LOG_FILE` | пусто | дополнительный файл с ротацией, всегда JSON |

Уровень root — `WARNING`: чужие библиотеки молчат, пока их не позовут
через `LOG_LEVELS`. Логгеры `vkt_bot`, `vkt_dispatcher`, `vkteams_client`
и `vkt_gitlab` получают уровень из `LOGGING`.

Бот и веб-сервер — разные процессы, поэтому в docker-compose у них разные
`SERVICE_NAME` (`vkt-bot`, `vkt-bot-server`) — иначе в Grafana их не
разделить.

## Секреты

Процессор `mask_secrets` работает на каждой строке:

- поле, в имени которого есть `token`, `password`, `secret`, `api_key`,
  `authorization`, `credential`, заменяется на `***` (только если значение
  строка: `access_token_expire_minutes` — это число минут);
- в строках маскируется значение query-параметра (`?token=…`) — токен
  приезжает в логи из URL, где имя поля ничего не подсказывает;
- пароль в DSN базы маскируется отдельно (`mask_url`), хост и база
  остаются видны.

Локальные переменные в трейсбеках выключены намеренно: они раздувают
строку и тащат в лог всё, что оказалось в области видимости.

## Loki и Grafana

Что важно на стороне сбора:

- **Одна строка — один JSON.** Трейсбек лежит в поле `exception`, а не
  многострочным хвостом, иначе promtail разрежет его на десяток «записей».
- **Метки — только низкой кардинальности:** `service`, `env`, `level`,
  `logger`. `chat_id`, `user_id`, `trace_id`, `request_id` — поля внутри
  JSON: их разбирают в запросе через `| json` или кладут в structured
  metadata. Метка с `chat_id` убивает Loki на первых тысячах чатов.
- Поле `message` дублирует `event` — панель логов Grafana показывает
  именно `message`, иначе в строке будет сырой JSON.

Пример scrape-конфига promtail для docker-compose:

```yaml
scrape_configs:
  - job_name: vkt-bot
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: [__meta_docker_container_label_com_docker_compose_service]
        target_label: service
    pipeline_stages:
      - json:
          expressions:
            level: level
            logger: logger
            timestamp: timestamp
      - labels:
          level:
          logger:
      - timestamp:
          source: timestamp
          format: RFC3339Nano
```

Запросы LogQL:

```logql
# всё по одной обработке события
{service="vkt-bot"} | json | trace_id="7f3c…"

# ошибки бота за сутки
{service="vkt-bot", level="error"}

# что происходило в конкретном чате
{service="vkt-bot"} | json | chat_id="694348323@chat.agent"

# сообщения, которые не ушли (ok:false от API)
{service="vkt-bot"} | json | event="message.send_failed"

# медленные запросы к панели
{service="vkt-bot-server"} | json | event="http.request" | duration_ms > 1000
```

## Sentry

`SENTRY_DSN` включает отправку: записи уровня ERROR доезжают через
штатную интеграцию SDK со stdlib. `environment` берётся из `ENV`,
`release` — из версии пакета, иначе события всех стендов сваливаются в
одну кучу.
