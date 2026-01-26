import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

export function setupApiErrorHandler() {
  const authStore = useAuthStore()
  const router = useRouter()

  // Handle 401 errors globally
  window.addEventListener('unhandledrejection', (event) => {
    const error = event.reason
    if (error?.status === 401) {
      authStore.logout()
      router.push('/login')
      event.preventDefault()
    }
  })
}
