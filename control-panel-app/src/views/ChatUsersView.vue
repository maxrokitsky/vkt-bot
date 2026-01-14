<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Eye } from 'lucide-vue-next'
import { listChatUsersApiChatUsersGetOptions } from '@/client/@tanstack/vue-query.gen'

const router = useRouter()
const page = ref(1)
const size = ref(20)

const { data: usersData, isLoading } = useQuery(
  computed(() => listChatUsersApiChatUsersGetOptions({
    query: { page: page.value, size: size.value },
  }))
)

const viewUserDetails = (userId: string) => {
  router.push(`/chat-users/${userId}`)
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-3xl font-bold">Пользователи чатов</h1>
    </div>

    <Table v-if="!isLoading && usersData">
      <TableHeader>
        <TableRow>
          <TableHead>ID пользователя</TableHead>
          <TableHead class="text-right">Действия</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="user in usersData.items" :key="user.id">
          <TableCell class="font-medium">{{ user.id }}</TableCell>
          <TableCell class="text-right">
            <Button
              variant="outline"
              size="sm"
              @click="viewUserDetails(user.id)"
            >
              <Eye class="h-4 w-4 mr-2" />
              Просмотр
            </Button>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
    <div v-else class="py-8 text-center">Загрузка...</div>

    <div v-if="usersData" class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Показано {{ usersData.items.length }} из {{ usersData.total }} пользователей
      </div>
      <div class="flex gap-2">
        <Button variant="outline" :disabled="page <= 1" @click="page--">Назад</Button>
        <Button variant="outline" :disabled="page >= usersData.pages" @click="page++">
          Далее
        </Button>
      </div>
    </div>
  </div>
</template>
