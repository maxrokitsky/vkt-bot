# Система динамических вебхуков для n8n

## Обзор

Система позволяет создавать динамические эндпоинты для отправки сообщений в чаты VK Teams через вебхуки из системы автоматизации n8n.

## Архитектура

### Компоненты

1. **Модель Webhook** - хранение информации о вебхуках в БД
2. **WebhookRepository** - CRUD операции и управление API ключами
3. **API для управления** - создание, просмотр, обновление, удаление вебхуков
4. **Публичные вебхуки** - эндпоинты для интеграции с n8n

### Безопасность

- API ключи хэшируются с помощью bcrypt
- Проверка ключей происходит внутри обработчиков (не через middleware)
- Rate limiting для защиты от злоупотреблений
- Логирование всех вызовов вебхуков

## API Эндпоинты

### Управление вебхуками (требует аутентификации)

```
GET    /api/webhooks                    - список вебхуков пользователя
POST   /api/webhooks                    - создание вебхука (возвращает API ключ!)
GET    /api/webhooks/{id}               - информация о вебхуке
PUT    /api/webhooks/{id}               - обновление вебхука
DELETE /api/webhooks/{id}               - удаление вебхука
POST   /api/webhooks/{id}/regenerate    - перегенерация API ключа
POST   /api/webhooks/{id}/send          - отправка сообщения (альтернативный путь)
```

### Публичные вебхуки (для интеграции с n8n)

```
POST   /webhooks/{webhook_id}           - отправка сообщения через вебхук
```

## Использование с n8n

### 1. Создание вебхука

**Запрос:**
```bash
POST /api/webhooks
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "Deploy Notifications",
  "chat_id": "123456789",
  "webhook_metadata": {
    "default_parse_mode": "MarkdownV2",
    "rate_limit": 10
  }
}
```

**Ответ:**
```json
{
  "webhook": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Deploy Notifications",
    "chat_id": "123456789",
    "created_by": "user123",
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "is_active": true,
    "webhook_metadata": {
      "default_parse_mode": "MarkdownV2",
      "rate_limit": 10
    }
  },
  "api_key": "abc123def456ghi789jkl012mno345pqr678stu901",
  "message": "Webhook created successfully. Save this API key - it won't be shown again."
}
```

### 2. Настройка n8n Webhook Node

**URL:**
```
https://your-bot-domain.com/webhooks/{webhook_id}
```

**Method:** POST

**Headers:**
```
Authorization: Bearer {api_key}
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "text": "✅ Развертывание успешно завершено!\n\nПроект: {{$json.project}}\nВерсия: {{$json.version}}\nСреда: {{$json.environment}}\nВремя: {{$json.timestamp}}",
  "parse_mode": "MarkdownV2",
  "inline_keyboard_markup": "[[{\"text\":\"Открыть пайплайн\",\"url\":\"{{$json.pipeline_url}}\"}]]"
}
```

### 3. Пример использования в n8n Workflow

1. **HTTP Request Node** - получает данные о деплое
2. **Function Node** - форматирует сообщение
3. **Webhook Node** - отправляет в VK Teams

**Пример Function Node:**
```javascript
const message = {
  text: `✅ *Развертывание успешно завершено!*\n\n` +
        `*Проект:* ${$json.project}\n` +
        `*Версия:* ${$json.version}\n` +
        `*Среда:* ${$json.environment}\n` +
        `*Время:* ${new Date().toLocaleString()}`,
  parse_mode: "MarkdownV2",
  inline_keyboard_markup: JSON.stringify([
    [
      {
        "text": "Открыть пайплайн",
        "url": $json.pipeline_url
      }
    ]
  ])
};

return message;
```

## Формат сообщений

### Поддерживаемые параметры

| Параметр | Тип | Описание | Обязательный |
|----------|-----|----------|--------------|
| text | string | Текст сообщения (до 4000 символов) | Да |
| parse_mode | string | Режим разметки: "MarkdownV2" или "HTML" | Нет |
| inline_keyboard_markup | string | JSON-строка с inline клавиатурой | Нет |

### Поддержка MarkdownV2

```markdown
*bold text*
_italic text_
[inline URL](http://www.example.com/)
[inline mention of a user](tg://user?id=123456789)
`inline fixed-width code`
```

### Inline клавиатуры

```json
[
  [
    {
      "text": "Кнопка 1",
      "url": "https://example.com"
    },
    {
      "text": "Кнопка 2",
      "callbackData": "action_2"
    }
  ],
  [
    {
      "text": "Кнопка 3",
      "url": "https://example2.com"
    }
  ]
]
```

## Безопасность

### API ключи

1. **Генерация**: При создании вебхука генерируется случайный API ключ
2. **Хранение**: Ключи хэшируются с помощью bcrypt
3. **Отображение**: Ключ показывается только один раз при создании
4. **Перегенерация**: Можно перегенерировать ключ через API

### Rate Limiting

По умолчанию: 10 запросов в минуту на вебхук.

### Логирование

Все вызовы вебхуков логируются:
- Успешные отправки
- Ошибки отправки
- Попытки неавторизованного доступа

## Расширенные возможности

### Шаблоны сообщений

В `webhook_metadata` можно хранить шаблоны:

```json
{
  "webhook_metadata": {
    "templates": {
      "deploy_success": "✅ Развертывание {project} в {environment} успешно завершено!",
      "deploy_failed": "❌ Ошибка развертывания {project} в {environment}: {error}"
    }
  }
}
```

### Валидация IP адресов

```json
{
  "webhook_metadata": {
    "allowed_ips": ["192.168.1.1", "10.0.0.0/8"]
  }
}
```

### Кастомные настройки

```json
{
  "webhook_metadata": {
    "default_parse_mode": "MarkdownV2",
    "rate_limit": 20,
    "timezone": "Europe/Moscow",
    "notify_users": ["user1", "user2"]
  }
}
```

## Примеры использования

### Уведомления о деплое

```json
{
  "text": "🚀 *Новый деплой!*\n\nПроект: backend-api\nВерсия: v1.2.3\nСреда: production\nИнициатор: {{$json.user}}\nСтатус: ✅ Успешно",
  "parse_mode": "MarkdownV2"
}
```

### Мониторинг ошибок

```json
{
  "text": "⚠️ *Обнаружена ошибка!*\n\nСервис: payment-service\nОшибка: Database connection failed\nУровень: CRITICAL\nВремя: {{$json.timestamp}}",
  "parse_mode": "MarkdownV2",
  "inline_keyboard_markup": "[[{\"text\":\"Открыть Grafana\",\"url\":\"https://grafana.example.com\"}]]"
}
```

### Ежедневные отчеты

```json
{
  "text": "📊 *Ежедневный отчет*\n\nНовых пользователей: {{$json.new_users}}\nТранзакций: {{$json.transactions}}\nОшибок: {{$json.errors}}\nДоход: {{$json.revenue}} руб.",
  "parse_mode": "MarkdownV2"
}
```

## Устранение неполадок

### Ошибки аутентификации

1. **401 Unauthorized** - неверный или отсутствующий API ключ
2. **404 Not Found** - вебхук не найден или неверный ID
3. **403 Forbidden** - вебхук неактивен

### Ошибки отправки

1. **500 Internal Server Error** - ошибка при отправке в VK Teams
2. **429 Too Many Requests** - превышен rate limit
3. **400 Bad Request** - неверный формат запроса

### Логи

Все ошибки логируются с деталями:
- ID вебхука
- ID чата
- Текст ошибки
- Время запроса

## Интеграция с фронтендом

Система вебхуков интегрирована с control-panel-app:

1. **Список вебхуков** - просмотр всех вебхуков пользователя
2. **Создание вебхука** - форма с выбором чата и настройками
3. **Управление вебхуками** - активация/деактивация, обновление
4. **Просмотр логов** - история вызовов вебхука

## Разработка

### Добавление новых функций

1. **Шаблоны переменных** - поддержка переменных в тексте сообщений
2. **Вложения** - отправка файлов через вебхуки
3. **Групповые вебхуки** - отправка в несколько чатов одновременно
4. **Webhook тестирование** - тестовые запросы из интерфейса

### Тестирование

```bash
# Создание тестового вебхука
curl -X POST http://localhost:8000/api/webhooks \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "chat_id": "123"}'

# Отправка тестового сообщения
curl -X POST http://localhost:8000/webhooks/<webhook_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message from n8n"}'
```