import type { Component } from 'vue'
import type { RouteRecordRaw, RouteRecordNormalized } from 'vue-router'

/** Ширина колонки контента. Таблицам нужен размах, формам — короткая строка. */
export type PageWidth = 'narrow' | 'medium' | 'wide'

/** Раздел бокового меню. Порядок массива — порядок в сайдбаре. */
export const NAV_GROUPS = [
  { id: 'overview', label: null },
  { id: 'people', label: 'Чаты и люди' },
  { id: 'integrations', label: 'Интеграции' },
  { id: 'admin', label: 'Управление' },
] as const

export type NavGroupId = (typeof NAV_GROUPS)[number]['id']

export interface NavEntry {
  group: NavGroupId
  order: number
  icon: Component
  /** Короткая подпись для палитры команд, если название неочевидно. */
  keywords?: string[]
}

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    description?: string
    width?: PageWidth
    requiresAuth?: boolean
    requiresAdmin?: boolean
    /** Имя родительского маршрута — из него строятся хлебные крошки. */
    parent?: string
    /** Пункт бокового меню. Маршруты без него в меню не попадают. */
    nav?: NavEntry
  }
}

export interface NavGroup {
  id: NavGroupId
  label: string | null
  items: {
    title: string
    path: string
    icon: Component
    keywords: string[]
  }[]
}

/**
 * Собрать меню из маршрутов.
 *
 * Единственный источник правды — `meta.nav`, поэтому пункт нельзя забыть
 * добавить или удалить вслед за маршрутом.
 */
export function navGroups(
  routes: (RouteRecordNormalized | RouteRecordRaw)[],
  { isAdmin }: { isAdmin: boolean },
): NavGroup[] {
  return NAV_GROUPS.map(({ id, label }) => ({
    id,
    label,
    items: routes
      .filter((route) => route.meta?.nav?.group === id)
      .filter((route) => isAdmin || !route.meta?.requiresAdmin)
      .sort((a, b) => a.meta!.nav!.order - b.meta!.nav!.order)
      .map((route) => ({
        title: route.meta!.title ?? '',
        path: route.path,
        icon: route.meta!.nav!.icon,
        keywords: route.meta!.nav!.keywords ?? [],
      })),
  })).filter((group) => group.items.length > 0)
}
