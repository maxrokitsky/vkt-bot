<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation } from '@tanstack/vue-query'
import { Bot } from 'lucide-vue-next'
import { getCurrentUserInfoApiAuthMeGet, loginApiAuthLoginPost } from '@/client'
import { useAuthStore } from '@/stores/auth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const token = ref('')
const error = ref('')
/** Переход по ссылке из сообщения бота: токен уже в адресе, форма не нужна. */
const fromLink = ref(false)

const redirectTarget = (route.query.redirect as string) || '/'

onMounted(() => {
  const urlToken = route.query.token as string
  if (!urlToken) return

  token.value = urlToken
  fromLink.value = true
  // Одноразовый токен не должен остаться в адресной строке и истории.
  const query = { ...route.query }
  delete query.token
  router.replace({ path: '/login', query })
  submit()
})

const login = useMutation({
  mutationFn: async () => {
    const response = await loginApiAuthLoginPost({ body: { token: token.value } })
    if (response.error) throw response.error
    return response.data
  },
  onSuccess: async (data) => {
    if (!data) return
    authStore.setToken(data.access_token)
    const me = await getCurrentUserInfoApiAuthMeGet()
    if (me.data) authStore.setUser(me.data)
    router.replace(redirectTarget)
  },
  onError: (err: unknown) => {
    fromLink.value = false
    const detail =
      (err as { error?: { detail?: string }; detail?: string })?.error?.detail ??
      (err as { detail?: string })?.detail
    if (detail === 'Token expired') {
      error.value = 'Срок токена истёк. Отправьте боту /login ещё раз.'
    } else if (detail === 'Token already used') {
      error.value = 'Этот токен уже использован. Отправьте боту /login ещё раз.'
    } else if (detail === 'Invalid token') {
      error.value = 'Токен не подошёл. Скопируйте его из сообщения бота целиком.'
    } else {
      error.value = 'Войти не удалось. Попробуйте ещё раз.'
    }
  },
})

const pending = computed(() => login.isPending.value)

function submit() {
  error.value = ''
  login.mutate()
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-background px-4 py-12">
    <div class="w-full max-w-sm space-y-8">
      <div class="space-y-3">
        <div
          class="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground"
        >
          <Bot class="size-5" />
        </div>
        <div class="space-y-1">
          <h1 class="text-xl font-semibold tracking-tight">Панель управления VKT Bot</h1>
          <p class="text-sm text-muted-foreground">
            Вход — по одноразовому токену от бота. Отправьте ему
            <code class="rounded bg-muted px-1 py-0.5 font-mono text-xs">/login</code>
            и откройте ссылку из ответа.
          </p>
        </div>
      </div>

      <div v-if="fromLink && pending" class="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner class="size-4" />
        Проверяем токен…
      </div>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="token">Токен</Label>
          <Input
            id="token"
            v-model="token"
            class="font-mono"
            placeholder="Вставьте токен из сообщения"
            autocomplete="off"
            required
            :disabled="pending"
          />
        </div>

        <Alert v-if="error" variant="destructive">
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <Button type="submit" class="w-full" :disabled="!token.trim() || pending">
          <Spinner v-if="pending" class="size-4" />
          Войти
        </Button>
      </form>
    </div>
  </div>
</template>
