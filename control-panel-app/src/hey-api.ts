import { client } from './client/client.gen'

/**
 * Адрес бэкенда. Он же нужен для публичных ссылок вебхуков, поэтому вынесен:
 * фронт в dev живёт на другом порту, и `window.location.origin` там врёт.
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8765'

client.setConfig({ baseUrl: API_BASE_URL })

const LOGIN_PATH = '/api/auth/login'

// Add request interceptor to include auth token
client.interceptors.request.use((request: Request) => {
  const url = new URL(request.url)
  // Don't add auth header to login endpoint
  if (url.pathname === LOGIN_PATH) {
    return request
  }
  const token = localStorage.getItem('token')
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`)
  }
  return request
})

/** Imported lazily so this module stays free of store/router import cycles. */
async function handleUnauthorized() {
  const { useAuthStore } = await import('@/stores/auth')
  const { default: router } = await import('@/router')

  useAuthStore().logout()

  const current = router.currentRoute.value
  if (current.path === '/login') return
  await router.replace({
    path: '/login',
    query: current.fullPath === '/' ? {} : { redirect: current.fullPath },
  })
}

// A rejected token must end the session instead of leaving an empty panel up.
client.interceptors.response.use((response: Response, request: Request) => {
  if (response.status === 401 && new URL(request.url).pathname !== LOGIN_PATH) {
    void handleUnauthorized()
  }
  return response
})
