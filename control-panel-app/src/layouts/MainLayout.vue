<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { LogOut, Users, MessageCircle, Shield, Home } from 'lucide-vue-next'

const authStore = useAuthStore()
const router = useRouter()

const userName = computed(() => authStore.user?.username || 'Пользователь')
const isAdmin = computed(() => authStore.isAdmin)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="border-b bg-white shadow-sm">
      <div class="container mx-auto flex h-16 items-center justify-between px-4">
        <div class="flex items-center gap-8">
          <RouterLink to="/" class="text-xl font-bold hover:text-gray-700 transition-colors">
            VKT Bot - Панель управления
          </RouterLink>
          <nav class="flex gap-6">
            <RouterLink
              to="/"
              class="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900"
              active-class="text-gray-900"
              exact
            >
              <Home class="h-4 w-4" />
              Главная
            </RouterLink>
            <RouterLink
              v-if="isAdmin"
              to="/users"
              class="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900"
              active-class="text-gray-900"
            >
              <Users class="h-4 w-4" />
              Пользователи
            </RouterLink>
            <RouterLink
              to="/chats"
              class="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900"
              active-class="text-gray-900"
            >
              <MessageCircle class="h-4 w-4" />
              Чаты
            </RouterLink>
            <RouterLink
              to="/roles"
              class="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-gray-900"
              active-class="text-gray-900"
            >
              <Shield class="h-4 w-4" />
              Роли
            </RouterLink>
          </nav>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-sm text-gray-600">{{ userName }}</span>
          <Button variant="outline" size="sm" @click="handleLogout">
            <LogOut class="mr-2 h-4 w-4" />
            Выход
          </Button>
        </div>
      </div>
    </header>

    <main class="container mx-auto flex-1 px-4 py-8">
      <RouterView />
    </main>

    <footer class="border-t bg-gray-50 py-4">
      <div class="container mx-auto px-4 text-center text-sm text-gray-600">
        VKT Bot Control Panel © 2025
      </div>
    </footer>
  </div>
</template>
