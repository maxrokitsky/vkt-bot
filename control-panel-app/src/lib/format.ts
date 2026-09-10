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
