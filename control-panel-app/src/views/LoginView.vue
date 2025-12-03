<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMutation } from '@tanstack/vue-query'
import { useAuthStore } from '@/stores/auth'
import { loginApiAuthLoginPost, getCurrentUserInfoApiAuthMeGet } from '@/client'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')

const loginMutation = useMutation({
  mutationFn: async () => {
    const response = await loginApiAuthLoginPost({
      body: {
        username: username.value,
        password: password.value,
      },
    })
    return response.data
  },
  onSuccess: async (data) => {
    if (data) {
      authStore.setToken(data.access_token)

      // Fetch user info
      const userResponse = await getCurrentUserInfoApiAuthMeGet()
      if (userResponse.data) {
        authStore.setUser(userResponse.data)
      }

      router.push('/')
    }
  },
  onError: () => {
    error.value = 'Неверное имя пользователя или пароль'
  },
})

const handleSubmit = () => {
  error.value = ''
  loginMutation.mutate()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <Card class="w-full max-w-md">
      <CardHeader>
        <CardTitle class="text-center text-3xl">Панель управления VKT Bot</CardTitle>
      </CardHeader>
      <CardContent>
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div class="space-y-2">
            <Label for="username">Имя пользователя</Label>
            <Input
              id="username"
              v-model="username"
              type="text"
              placeholder="Введите имя пользователя"
              required
            />
          </div>
          <div class="space-y-2">
            <Label for="password">Пароль</Label>
            <Input
              id="password"
              v-model="password"
              type="password"
              placeholder="Введите пароль"
              required
            />
          </div>
          <div v-if="error" class="text-sm text-red-600">{{ error }}</div>
          <Button type="submit" class="w-full" :disabled="loginMutation.isPending.value">
            {{ loginMutation.isPending.value ? 'Вход...' : 'Войти' }}
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
