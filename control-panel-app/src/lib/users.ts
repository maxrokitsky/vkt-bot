/**
 * Инициалы для аватара-заглушки: «Иван Петров» → «ИП», а для id вида
 * `ivan.petrov@example.com` — «IP». Аватарок у VK Teams API нет, показывать
 * нечего, кроме букв.
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
