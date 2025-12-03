<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Users, MessageCircle, Shield } from 'lucide-vue-next'

const authStore = useAuthStore()
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold">Добро пожаловать, {{ authStore.user?.username }}!</h1>
      <!-- <p class="text-muted-foreground mt-2">
      </p> -->
    </div>

    <div class="grid gap-4 md:grid-cols-3">
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Пользователи</CardTitle>
          <Users class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <p class="text-sm text-muted-foreground">Управление пользователями системы</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Чаты</CardTitle>
          <MessageCircle class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <p class="text-sm text-muted-foreground">Просмотр чатов бота</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Роли</CardTitle>
          <Shield class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <p class="text-sm text-muted-foreground">Управление ролями и участниками</p>
        </CardContent>
      </Card>
    </div>

  </div>
</template>
