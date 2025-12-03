# Web API Quick Start

Быстрый старт для работы с веб-API бота.

## 1. Настройка (5 минут)

### Шаг 1: Добавить SECRET_KEY в .env

```bash
# Сгенерировать и добавить в .env
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
```

### Шаг 2: Применить миграции

```bash
alembic upgrade head
```

### Шаг 3: Создать первого админа

```bash
uv run python -m vkt_bot.scripts.create_admin admin MyPassword123 admin@example.com
```

Запомните username и password - они понадобятся для входа!

## 2. Запуск сервера

```bash
uv run server
```

Сервер запустится на `http://localhost:8000`

## 3. Тестирование API

### Вариант 1: Swagger UI (рекомендуется для начала)

1. Откройте в браузере: http://localhost:8000/docs
2. Нажмите на "Authorize" (замок справа вверху)
3. Сначала выполните `POST /api/auth/login`:
   - Нажмите "Try it out"
   - Введите username и password
   - Нажмите "Execute"
   - Скопируйте `access_token` из ответа
4. Нажмите "Authorize" и вставьте токен в поле "Value" (с префиксом "Bearer "):
   ```
   Bearer ваш-токен-здесь
   ```
5. Теперь можно тестировать любые endpoints!

### Вариант 2: curl

```bash
# 1. Получить токен
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"MyPassword123"}' \
  | jq -r '.access_token')

# 2. Проверить текущего пользователя
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq

# 3. Список пользователей
curl http://localhost:8000/api/users \
  -H "Authorization: Bearer $TOKEN" | jq

# 4. Список чатов
curl http://localhost:8000/api/chats \
  -H "Authorization: Bearer $TOKEN" | jq

# 5. Список ролей
curl http://localhost:8000/api/roles \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Вариант 3: Python скрипт

```bash
# Отредактируйте examples/test_api.py - укажите свой пароль
# Затем запустите:
python examples/test_api.py
```

## 4. Основные операции

### Создать нового пользователя

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "password123",
    "is_superuser": false,
    "is_active": true
  }'
```

### Создать роль

```bash
curl -X POST http://localhost:8000/api/roles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Moderator"}'
```

### Добавить участника в роль

```bash
# Получите role_id из предыдущего запроса
curl -X POST http://localhost:8000/api/roles/{role_id}/members \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'
```

## 5. Полная документация

- **Swagger UI:** http://localhost:8000/docs (интерактивная)
- **ReDoc:** http://localhost:8000/redoc (читабельная)
- **Подробная документация:** [src/vkt_bot/webapp/README.md](src/vkt_bot/webapp/README.md)

## Частые проблемы

### "Could not validate credentials"
- Проверьте, что токен не истёк (по умолчанию 8 дней)
- Убедитесь, что добавили `Bearer ` перед токеном
- Получите новый токен через `/api/auth/login`

### "Not enough permissions"
- Убедитесь, что пользователь - админ (`is_superuser: true`)
- Создайте нового админа: `uv run python -m vkt_bot.scripts.create_admin ...`

### "User not found"
- Для User (веб-панель) - используйте username
- Для ChatUser (VK Teams) - используйте ID из чата

### Сервер не запускается
- Проверьте, что `SECRET_KEY` добавлен в `.env`
- Проверьте подключение к БД (`DB_URL` в `.env`)
- Примените миграции: `alembic upgrade head`

## Что дальше?

1. **Изучите все endpoints** в Swagger UI: http://localhost:8000/docs
2. **Прочитайте полную документацию**: [webapp/README.md](src/vkt_bot/webapp/README.md)
3. **Разработайте фронтенд** или используйте API напрямую из ваших приложений
4. **Настройте CORS** в `webapp/app.py` для продакшена
5. **Добавьте свои endpoints** следуя существующей структуре

---

**Нужна помощь?** Все детали в [WEBAPP_SUMMARY.md](WEBAPP_SUMMARY.md)
