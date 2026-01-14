import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/client'
import { getCurrentUserInfoApiAuthMeGet } from '@/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserResponse | null>(null)
  const isLoading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_superuser ?? false)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(newUser: UserResponse) {
    user.value = newUser
  }

  async function fetchUser() {
    if (!token.value || user.value) return

    isLoading.value = true
    try {
      const response = await getCurrentUserInfoApiAuthMeGet()
      if (response.data) {
        user.value = response.data
      }
    } catch {
      logout()
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    isLoading,
    setToken,
    setUser,
    fetchUser,
    logout,
  }
})
