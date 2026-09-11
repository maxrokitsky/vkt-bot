/**
 * Инициалы для аватара: «Иван Петров» → «ИП», а для id вида
 * `ivan.petrov@example.com` — «IP». Нужны, когда картинки нет: аватар
 * приносит `chats/getInfo`, но он есть не у всех, да и ссылка на него
 * может отдавать «Avatar not found».
 */
export function initials(name: string): string {
  return name
    .split(/[\s.@_-]+/)
    .filter(Boolean)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}
