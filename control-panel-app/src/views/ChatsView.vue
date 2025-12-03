<script setup lang="ts">
import { ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { listChatsApiChatsGet } from '@/client'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Search } from 'lucide-vue-next'

const page = ref(1)
const size = ref(10)
const searchQuery = ref('')

const { data: chatsData, isLoading } = useQuery({
  queryKey: ['chats', page, size],
  queryFn: async () => {
    const response = await listChatsApiChatsGet({
      query: { page: page.value, size: size.value },
    })
    return response.data
  },
})
</script>

<template>
  <div class="space-y-6">
    <!-- <div class="flex items-center justify-between">
      <h1 class="text-3xl font-bold">Чаты</h1>
    </div> -->

    <!-- <Card>
      <CardContent class="pt-6"> -->
        <div class="mb-4">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              v-model="searchQuery"
              placeholder="Поиск по названию чата..."
              class="pl-9"
            />
          </div>
        </div>

        <Table v-if="!isLoading && chatsData">
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Название</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="chat in chatsData.items.filter(
                (c) => !searchQuery || c.title?.toLowerCase().includes(searchQuery.toLowerCase()),
              )"
              :key="chat.id"
            >
              <TableCell class="font-mono text-sm">{{ chat.id }}</TableCell>
              <TableCell>{{ chat.title || '—' }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div v-else class="py-8 text-center">Загрузка...</div>
      <!-- </CardContent>
    </Card> -->

    <div v-if="chatsData" class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Показано {{ chatsData.items.length }} из {{ chatsData.total }} чатов
      </div>
      <div class="flex gap-2">
        <Button variant="outline" :disabled="page <= 1" @click="page--">Назад</Button>
        <Button variant="outline" :disabled="page >= chatsData.pages" @click="page++">
          Далее
        </Button>
      </div>
    </div>
  </div>
</template>
