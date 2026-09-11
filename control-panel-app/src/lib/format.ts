const dateTime = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const timeOnly = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const dayMonth = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
const relative = new Intl.RelativeTimeFormat('ru-RU', { numeric: 'auto' })

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

/** Дата и время: 09.09.2026, 14:03. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return dateTime.format(new Date(value))
}

/** Только время — для событий сегодняшнего дня. */
export function formatTime(value: string | Date): string {
  return timeOnly.format(new Date(value))
}

/**
 * `2026-09-11` как локальная календарная дата.
 *
 * `new Date('2026-09-11')` — это полночь UTC, и западнее Гринвича график
 * рисует предыдущий день. Дата без времени — про календарь, а не про
 * момент, поэтому собираем её из частей.
 */
export function parseLocalDate(value: string): Date {
  const parts = value.split('-').map(Number)
  if (parts.length !== 3 || parts.some(Number.isNaN)) return new Date(value)
  const [year, month, day] = parts as [number, number, number]
  return new Date(year, month - 1, day)
}

/** «9 сент.» — подписи оси графика. */
export function formatDayMonth(value: string | Date): string {
  return dayMonth.format(new Date(value))
}

/** «3 часа назад». Для свежих событий короче и понятнее абсолютного времени. */
export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const seconds = (new Date(value).getTime() - Date.now()) / 1000
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) {
      return relative.format(Math.round(seconds / size), unit)
    }
  }
  return relative.format(Math.round(seconds), 'second')
}
