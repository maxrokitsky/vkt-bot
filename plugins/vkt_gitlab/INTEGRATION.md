# Интеграция Frontend компонентов GitLab плагина

Этот документ описывает, как интегрировать frontend компоненты плагина в основное приложение.

## Автоматическая интеграция (рекомендуется)

При разработке плагина используйте следующую структуру:

### 1. Размещение компонентов

Храните Vue компоненты в директории плагина:
```
plugins/vkt_gitlab/frontend/views/GitLabWebhooksView.vue
```

### 2. Копирование в основное приложение

После изменений скопируйте компонент:
```bash
cp plugins/vkt_gitlab/frontend/views/GitLabWebhooksView.vue \
   control-panel-app/src/views/GitLabWebhooksView.vue
```

### 3. Регистрация маршрута

В `control-panel-app/src/router/index.ts`:

```typescript
import GitLabWebhooksView from '@/views/GitLabWebhooksView.vue'

// В массиве children MainLayout:
{
  path: 'gitlab/webhooks',
  name: 'gitlab-webhooks',
  component: GitLabWebhooksView,
  meta: { title: "GitLab Webhooks", requiresAuth: true, requiresAdmin: true },
}
```

### 4. Добавление в sidebar

В `control-panel-app/src/components/AppSidebar.vue`:

```typescript
import { IconWebhook } from "@tabler/icons-vue"

// В массиве navMain:
...(isAdmin.value ? [{
  title: "GitLab Webhooks",
  url: "/gitlab/webhooks",
  icon: IconWebhook,
}] : []),
```

### 5. Регенерация API клиента

После изменений в backend API:
```bash
cd control-panel-app
pnpm openapi-ts
```

## Структура файлов

После интеграции структура будет следующей:

```
vkt-bot/
├── plugins/vkt_gitlab/
│   ├── src/vkt_gitlab/           # Backend код
│   │   ├── api.py                # FastAPI endpoints
│   │   ├── models.py             # DB модели
│   │   └── schemas.py            # Pydantic схемы
│   └── frontend/                 # Frontend исходники
│       └── views/
│           └── GitLabWebhooksView.vue
│
└── control-panel-app/
    └── src/
        ├── views/
        │   └── GitLabWebhooksView.vue  # Скопированный компонент
        ├── router/
        │   └── index.ts                # С добавленным маршрутом
        └── components/
            └── AppSidebar.vue          # С добавленным пунктом меню
```

## Важные заметки

1. **Исходник vs Рабочая копия**: Храните исходный компонент в `plugins/vkt_gitlab/frontend/`, а в `control-panel-app/src/views/` только рабочую копию.

2. **Синхронизация**: При изменении компонента в плагине не забывайте копировать его в основное приложение.

3. **API клиент**: После любых изменений в `api.py` обязательно регенерируйте API клиент командой `pnpm openapi-ts`.

4. **Git**: Рекомендуется коммитить оба файла (исходник в плагине и копию в приложении) для полной истории изменений.

## Скрипт автоматизации (опционально)

Можно создать скрипт для автоматического копирования:

```bash
#!/bin/bash
# scripts/sync-gitlab-frontend.sh

cp plugins/vkt_gitlab/frontend/views/GitLabWebhooksView.vue \
   control-panel-app/src/views/GitLabWebhooksView.vue

echo "GitLab frontend components synced!"
```

Использование:
```bash
chmod +x scripts/sync-gitlab-frontend.sh
./scripts/sync-gitlab-frontend.sh
```
