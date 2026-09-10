import type { ActorType, EventSeverity, EventSource } from '@/client'
import type { BadgeVariants } from '@/components/ui/badge'

/** Подписи журнала событий — общие для ленты, обзора и карточек. */
export const SOURCE_LABELS: Record<EventSource, string> = {
  panel: 'Панель',
  command: 'Команда в чате',
  api: 'Событие чата',
  bot: 'Бот',
  webhook: 'Вебхук',
  plugin: 'Плагин',
  system: 'Система',
}

export const ACTOR_LABELS: Record<ActorType, string> = {
  user: 'Человек',
  bot: 'Бот',
  system: 'Система',
  external: 'Внешняя система',
}

export const SEVERITY_LABELS: Record<EventSeverity, string> = {
  debug: 'Отладка',
  info: 'Событие',
  warning: 'Предупреждение',
  error: 'Ошибка',
}

type Variant = BadgeVariants['variant']

/** Цветом выделяется то, что требует внимания, остальное спокойно. */
export const SEVERITY_VARIANTS: Record<EventSeverity, Variant> = {
  debug: 'outline',
  info: 'secondary',
  warning: 'outline',
  error: 'destructive',
}

/** Домен типа: `role.assigned` → `role`. По нему фильтруют чаще, чем по типу. */
export function eventDomain(type: string): string {
  return type.split('.')[0] ?? type
}
