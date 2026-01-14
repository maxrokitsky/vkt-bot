<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation } from '@tanstack/vue-query'
import { useAuthStore } from '@/stores/auth'
import { loginApiAuthLoginPost, getCurrentUserInfoApiAuthMeGet } from '@/client'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const token = ref('')
const error = ref('')

onMounted(() => {
  const urlToken = route.query.token as string
  if (urlToken) {
    token.value = urlToken
    handleSubmit()
  }
})

const loginMutation = useMutation({
  mutationFn: async () => {
    const response = await loginApiAuthLoginPost({
      body: {
        token: token.value,
      },
    })
    if (response.error) {
      throw response.error
    }
    return response.data
  },
  onSuccess: async (data) => {
    if (data) {
      authStore.setToken(data.access_token)

      const userResponse = await getCurrentUserInfoApiAuthMeGet()
      if (userResponse.data) {
        authStore.setUser(userResponse.data)
      }

      router.push('/')
    }
  },
  onError: (err: unknown) => {
    // hey-api returns error in err.error.detail or err.detail
    const errObj = err as { error?: { detail?: string }; detail?: string }
    const detail = errObj?.error?.detail || errObj?.detail
    if (detail === 'Token expired') {
      error.value = 'Токен просрочен. Запросите новый командой /login'
    } else if (detail === 'Token already used') {
      error.value = 'Токен уже использован. Запросите новый командой /login'
    } else if (detail === 'Invalid token') {
      error.value = 'Неверный токен'
    } else {
      error.value = 'Ошибка входа. Попробуйте ещё раз'
    }
  },
})

const handleSubmit = () => {
  error.value = ''
  loginMutation.mutate()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md space-y-6">
      <div class="text-center">
        <h1 class="text-2xl font-bold">Панель управления VKT Bot</h1>
        <p class="mt-2 text-muted-foreground">
          Введите токен, полученный от бота командой /login
        </p>
      </div>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <Input
          v-model="token"
          type="text"
          placeholder="Введите токен"
          class="font-mono"
          required
        />
        <div v-if="error" class="text-sm text-red-600">{{ error }}</div>
        <Button type="submit" class="w-full" :disabled="loginMutation.isPending.value">
          {{ loginMutation.isPending.value ? 'Вход...' : 'Войти' }}
        </Button>
      </form>
    </div>
  </div>
</template>
