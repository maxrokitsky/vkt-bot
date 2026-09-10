/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Адрес бэкенда. По умолчанию — локальный сервер на 8765. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
