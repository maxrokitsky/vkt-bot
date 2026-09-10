<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { MessagesSquare, Send } from 'lucide-vue-next'
import { listChatsApiChatsGetOptions } from '@/client/@tanstack/vue-query.gen'
import type { ChatResponse } from '@/client'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import DataToolbar from '@/components/data/DataToolbar.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import RowActions from '@/components/data/RowActions.vue'
import SendMessageDialog from '@/components/SendMessageDialog.vue'
import { Badge } from '@/components/ui/badge'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useListQuery } from '@/composables/useListQuery'
import { chatTypeLabel } from '@/lib/chats'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)
const { page, pageSize, searchInput, search } = useListQuery()

const chatToMessage = ref<ChatResponse | null>(null)

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listChatsApiChatsGetOptions({
      query: { page: page.value, size: pageSize.value, search: search.value || undefined },
    }),
  ),
)
</script>

<template>
  <div>
    <PageHeader />

    <DataToolbar
      v-model:search="searchInput"
      placeholder="Название или id чата"
    />

    <DataTableShell
      :loading="isPending"
      :error="isError ? true : undefined"
      :empty="!data?.items.length"
      :columns="isAdmin ? 3 : 2"
      :empty-icon="MessagesSquare"
      :empty-title="search ? 'Чат не нашёлся' : 'Бот пока не в одном чате'"
      :empty-description="
        search
          ? 'Проверьте название или попробуйте id.'
          : 'Чат появится здесь, как только бота добавят в него.'
      "
      @retry="refetch()"
    >
      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead>Название</TableHead>
            <TableHead class="w-32">Тип</TableHead>
            <TableHead v-if="isAdmin" class="w-16 text-right">
              <span class="sr-only">Действия</span>
            </TableHead>
          </TableRow>
        </TableHeader>
      </template>

      <template #body>
        <TableBody>
          <TableRow v-for="chat in data?.items ?? []" :key="chat.id">
            <TableCell>
              <div class="font-medium">{{ chat.title || 'Без названия' }}</div>
              <CopyableId :value="chat.id" :max="40" />
            </TableCell>
            <TableCell>
              <Badge variant="outline">{{ chatTypeLabel(chat.type) }}</Badge>
            </TableCell>
            <TableCell v-if="isAdmin" class="text-right">
              <RowActions>
                <DropdownMenuItem @click="chatToMessage = chat">
                  <Send />
                  Отправить сообщение
                </DropdownMenuItem>
              </RowActions>
            </TableCell>
          </TableRow>
        </TableBody>
      </template>
    </DataTableShell>

    <TablePagination
      v-if="data"
      :page="page"
      :size="pageSize"
      :total="data.total"
      :pages="data.pages"
      items-label="чатов"
      @update:page="page = $event"
    />

    <SendMessageDialog :chat="chatToMessage" @update:chat="chatToMessage = $event" />
  </div>
</template>
