import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/client'
import { getCurrentUserInfoApiAuthMeGet } from '@/client'

/** Read the `exp` claim without pulling in a JWT library. */
function tokenExpiry(jwt: string): number | null {
  const payload = jwt.split('.')[1]
  if (!payload) return null
  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const exp = JSON.parse(atob(padded)).exp
    return typeof exp === 'number' ? exp : null
  } catch {
    return null
  }
}

function isUsable(jwt: string | null): boolean {
  if (!jwt) return false
  const exp = tokenExpiry(jwt)
  // A token we cannot parse is not trusted; the server is the final say anyway.
  if (exp === null) return false
  return exp * 1000 > Date.now()
}

export const useAuthStore = defineStore('auth', () => {
  const stored = localStorage.getItem('token')
  const token = ref<string | null>(isUsable(stored) ? stored : null)
  const user = ref<UserResponse | null>(null)
  const isLoading = ref(false)

  // Drop a token that was already dead on load.
  if (stored && !token.value) localStorage.removeItem('token')

  let verification: Promise<boolean> | null = null

  const hasToken = computed(() => isUsable(token.value))
  // Authenticated means: a live token AND a user the server has confirmed.
  const isAuthenticated = computed(() => hasToken.value && user.value !== null)
  const isOwner = computed(() => user.value?.is_owner ?? false)
  const isAdmin = computed(() => user.value?.is_superuser || isOwner.value)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(newUser: UserResponse) {
    user.value = newUser
  }

  /**
   * Resolve the current user, asking the server once and caching the result.
   * Returns false — and clears the session — when the token is not valid.
   */
  async function ensureUser(): Promise<boolean> {
    if (!hasToken.value) {
      logout()
      return false
    }
    if (user.value) return true
    if (!verification) {
      verification = (async () => {
        isLoading.value = true
        try {
          const response = await getCurrentUserInfoApiAuthMeGet()
          if (response.data) {
            user.value = response.data
            return true
          }
          logout()
          return false
        } catch {
          logout()
          return false
        } finally {
          isLoading.value = false
          verification = null
        }
      })()
    }
    return verification
  }

  function logout() {
    token.value = null
    user.value = null
    verification = null
    localStorage.removeItem('token')
  }

  return {
    token,
    user,
    hasToken,
    isAuthenticated,
    isOwner,
    isAdmin,
    isLoading,
    setToken,
    setUser,
    ensureUser,
    logout,
  }
})
