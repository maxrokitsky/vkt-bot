# CLAUDE.md

Указания Claude Code (claude.ai/code) для работы с панелью управления.
Общее по репозиторию — в корневом [CLAUDE.md](../CLAUDE.md).

## Что это

SPA управления ботом: Vue 3 + TypeScript, Vue Router, Pinia, TanStack Query,
Tailwind CSS v4, shadcn-vue. Клиент API генерируется из OpenAPI-схемы бэкенда
через Hey API — руками не пишется.

## Команды

```bash
pnpm install       # первая установка
pnpm dev           # дев-сервер, http://localhost:5173
pnpm build         # сборка (внутри прогоняет type-check)
pnpm type-check    # vue-tsc
pnpm lint          # oxlint + eslint
pnpm format        # prettier по src/
pnpm openapi-ts    # перегенерация клиента из openapi.json
```

Перед коммитом `pnpm type-check`, `pnpm lint` и `pnpm build` должны быть
зелёными.

## Связь с бэкендом

- Клиент перегенерируется целиком командой `make generate_client` из корня:
  она экспортирует `openapi.json` и запускает `openapi-ts`. Тест
  `tests/webapp/test_openapi.py` падает, если схема в репозитории отстала от
  приложения.
- Адрес бэкенда — `API_BASE_URL` в `src/hey-api.ts`: берётся из
  `VITE_API_BASE_URL`, по умолчанию `http://localhost:8765`. Он же нужен для
  публичных ссылок вебхуков — `window.location.origin` в dev врёт, потому что
  фронт живёт на другом порту.
- Токен JWT хранится в localStorage.
- Новое поле в ответе API делайте обязательным (без значения по умолчанию),
  иначе в TypeScript оно станет опциональным и по всему фронту расползутся
  `?.`.

## Структура `src/`

- `components/layout/` — хром панели: `AppSidebar`, `AppHeader`,
  `AppBreadcrumbs`, `CommandPalette`, и каркас страницы: `PageContainer`,
  `PageHeader`, `PageSection`, `FieldRow`, `StickySaveBar`.
- `components/data/` — общие примитивы списков: `DataToolbar`,
  `DataTableShell` (рамка, залипающая шапка и три состояния — загрузка,
  ошибка, пусто), `TablePagination`, `EmptyState`, `CopyableId`,
  `RowActions`, `StatTile`.
- `components/ui/` — вендоренный shadcn-vue: ставится и обновляется через CLI,
  руками не правится (для него в `eslint.config.ts` отдельный блок правил).
- `composables/` — `useListQuery` (страница + поиск с задержкой),
  `useConfirm` (цель и открытость подтверждающего диалога — держать их в
  одном ref нельзя, см. комментарий в файле), `useCommandPalette`, `useTheme`.
- `lib/` — `format` (даты), `plural` (склонения), `audit` и `chats` (подписи
  перечислений API по-русски).
- `views/` — страницы, по одной на маршрут.

## Правила страниц

- Заголовок на странице ровно один — `PageHeader`; в шапке приложения только
  хлебные крошки. Название и описание берутся из `meta` маршрута.
- Контент не на всю ширину: `PageContainer` центрирует колонку, ширину задаёт
  `meta.width` маршрута — `wide` (84rem, таблицы), `medium` (64rem, карточки),
  `narrow` (42rem, формы и настройки).
- Меню сайдбара и палитра команд (`⌘K`) строятся из `router.getRoutes()` по
  `meta.nav` (`router/nav.ts`) — второго списка пунктов не существует.
- Компонент `Card` используем реже: разделы группируются `PageSection` с
  правилом-разделителем.
- Действия строки — в меню `RowActions` (`⋯`), а не рядом кнопками.
- Счётчик найденного живёт в `TablePagination`, в `DataToolbar` его нет.
