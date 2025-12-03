<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation } from '@tanstack/vue-query'
import { listChatsApiChatsGet, sendMessageApiChatsChatIdSendMessagePost } from '@/client'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Search, Send } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const page = ref(1)
const size = ref(10)
const searchQuery = ref('')
const showSendMessageDialog = ref(false)
const selectedChatId = ref('')
const selectedChatTitle = ref('')
const messageText = ref('')
const parseMode = ref<'MarkdownV2' | 'HTML' | undefined>(undefined)

const { data: chatsData, isLoading } = useQuery({
  queryKey: ['chats', page, size],
  queryFn: async () => {
    const response = await listChatsApiChatsGet({
      query: { page: page.value, size: size.value },
    })
    return response.data
  },
})

const sendMessageMutation = useMutation({
  mutationFn: async (data: { chatId: string; text: string; parseMode?: 'MarkdownV2' | 'HTML' }) => {
    return await sendMessageApiChatsChatIdSendMessagePost({
      path: { chat_id: data.chatId },
      body: {
        text: data.text,
        parse_mode: data.parseMode,
      },
    })
  },
  onSuccess: () => {
    showSendMessageDialog.value = false
    messageText.value = ''
    parseMode.value = undefined
    toast.success('Сообщение отправлено')
  },
  onError: (error) => {
    toast.error(`Не удалось отправить сообщение: ${error.message}`)
  },
})

const openSendMessageDialog = (chatId: string, chatTitle: string | null | undefined) => {
  selectedChatId.value = chatId
  selectedChatTitle.value = chatTitle || chatId
  showSendMessageDialog.value = true
}

const handleSendMessage = () => {
  if (!messageText.value.trim()) return

  sendMessageMutation.mutate({
    chatId: selectedChatId.value,
    text: messageText.value,
    parseMode: parseMode.value,
  })
}
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
              <TableHead class="w-[100px]">Действия</TableHead>
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
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  @click="openSendMessageDialog(chat.id, chat.title)"
                >
                  <Send class="h-4 w-4" />
                </Button>
              </TableCell>
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

    <!-- Диалог отправки сообщения -->
    <Dialog v-model:open="showSendMessageDialog">
      <DialogContent class="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Отправить сообщение</DialogTitle>
          <DialogDescription>
            Отправка сообщения в чат: {{ selectedChatTitle }}
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4">
          <div class="space-y-2">
            <label class="text-sm font-medium">Текст сообщения</label>
            <Textarea
              v-model="messageText"
              placeholder="Введите текст сообщения..."
              class="min-h-[150px]"
              :disabled="sendMessageMutation.isPending.value"
            />
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium">Режим парсинга (опционально)</label>
            <Select v-model="parseMode">
              <SelectTrigger>
                <SelectValue placeholder="Без форматирования" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem :value="undefined">Без форматирования</SelectItem>
                <SelectItem value="MarkdownV2">MarkdownV2</SelectItem>
                <SelectItem value="HTML">HTML</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="flex gap-2">
            <Button
              @click="handleSendMessage"
              :disabled="!messageText.trim() || sendMessageMutation.isPending.value"
              class="flex-1"
            >
              <Send class="h-4 w-4 mr-2" />
              Отправить
            </Button>
            <Button
              variant="outline"
              @click="showSendMessageDialog = false"
              :disabled="sendMessageMutation.isPending.value"
            >
              Отмена
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
