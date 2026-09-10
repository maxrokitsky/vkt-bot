import type { SessionStatus } from '@/client'
import type { BadgeVariants } from '@/components/ui/badge'

/** Подписи состояний диалога с агентом. */
export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  active: 'В работе',
  waiting_approval: 'Ждёт подтверждения',
  done: 'Ответил',
  failed: 'Сорвалась',
  canceled: 'Отменена',
}

type Variant = BadgeVariants['variant']

/** Цветом выделяется только то, что требует внимания. */
export const SESSION_STATUS_VARIANTS: Record<SessionStatus, Variant> = {
  active: 'outline',
  waiting_approval: 'outline',
  done: 'secondary',
  failed: 'destructive',
  canceled: 'outline',
}

const compact = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 })

/**
 * Токены в коротком виде: 128 400 → «128,4 тыс.».
 *
 * Точное число здесь не нужно — важен порядок, а длинные цифры распирают
 * колонку таблицы.
 */
export function formatTokens(value: number): string {
  return compact.format(value)
}

/** Роль в диалоге: наружу отдаются только эти две. */
export const MESSAGE_ROLE_LABELS: Record<string, string> = {
  user: 'Вопрос',
  assistant: 'Агент',
}
