import type { ChatType } from '@/client'

/** Тип чата по-русски — в API он приходит английским значением. */
export const CHAT_TYPE_LABELS: Record<ChatType, string> = {
  private: 'личный',
  group: 'группа',
  channel: 'канал',
}

export function chatTypeLabel(type: ChatType | string): string {
  return CHAT_TYPE_LABELS[type as ChatType] ?? type
}
