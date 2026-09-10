import type { ActionType, ActorType, EntityType } from '@/client'
import type { BadgeVariants } from '@/components/ui/badge'

/** Подписи журнала — общие для страницы журнала и обзора. */
export const ACTOR_LABELS: Record<ActorType, string> = {
  web_user: 'Панель',
  bot_user: 'Бот',
  system: 'Система',
}

export const ACTION_LABELS: Record<ActionType, string> = {
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление',
  assign: 'Назначение',
  unassign: 'Снятие',
}

export const ENTITY_LABELS: Record<EntityType, string> = {
  user: 'Пользователь',
  chat_user: 'Участник',
  role: 'Роль',
  chat: 'Чат',
  role_assignment: 'Назначение роли',
  chat_membership: 'Состав чата',
  bot_settings: 'Настройка',
}

type Variant = BadgeVariants['variant']

/** Цвет отражает необратимость: удаление — красным, остальное спокойно. */
export const ACTION_VARIANTS: Record<ActionType, Variant> = {
  create: 'secondary',
  update: 'outline',
  delete: 'destructive',
  assign: 'secondary',
  unassign: 'outline',
}
