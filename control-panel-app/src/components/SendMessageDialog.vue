<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMutation } from '@tanstack/vue-query'
import { Send } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { sendMessageApiChatsChatIdSendMessagePostMutation } from '@/client/@tanstack/vue-query.gen'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'

/** Отправка от лица бота. Вынесено из списка чатов, чтобы переиспользовать. */
const props = defineProps<{
  chat: { id: string; title?: string | null } | null
}>()

const emit = defineEmits<{ 'update:chat': [null] }>()

const MAX_LENGTH = 4096

const text = ref('')
const parseMode = ref<'plain' | 'MarkdownV2' | 'HTML'>('plain')

watch(
  () => props.chat,
  (chat) => {
    if (chat) {
      text.value = ''
      parseMode.value = 'plain'
    }
  },
)

const send = useMutation({
  ...sendMessageApiChatsChatIdSendMessagePostMutation(),
  onSuccess: () => {
    toast.success('Сообщение отправлено')
    emit('update:chat', null)
  },
  onError: () => toast.error('Сообщение не отправлено'),
})

function submit() {
  if (!props.chat || !text.value.trim()) return
  send.mutate({
    path: { chat_id: props.chat.id },
    body: {
      text: text.value,
      parse_mode: parseMode.value === 'plain' ? undefined : parseMode.value,
    },
  })
}
</script>

<template>
  <Dialog :open="chat !== null" @update:open="emit('update:chat', null)">
    <DialogContent class="sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>Отправить сообщение</DialogTitle>
        <DialogDescription>
          От лица бота в «{{ chat?.title || chat?.id }}»
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div class="space-y-2">
          <Label for="message">Текст</Label>
          <Textarea
            id="message"
            v-model="text"
            :maxlength="MAX_LENGTH"
            placeholder="Что отправить в чат"
            class="min-h-40"
            :disabled="send.isPending.value"
          />
          <p class="text-right text-xs tabular-nums text-muted-foreground">
            {{ text.length }} / {{ MAX_LENGTH }}
          </p>
        </div>

        <div class="space-y-2">
          <Label for="parse-mode">Форматирование</Label>
          <Select v-model="parseMode">
            <SelectTrigger id="parse-mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="plain">Без форматирования</SelectItem>
              <SelectItem value="MarkdownV2">MarkdownV2</SelectItem>
              <SelectItem value="HTML">HTML</SelectItem>
            </SelectContent>
          </Select>
          <p v-if="parseMode === 'MarkdownV2'" class="text-xs text-muted-foreground">
            Спецсимволы нужно экранировать, иначе VK Teams отклонит сообщение.
          </p>
        </div>
      </div>

      <DialogFooter>
        <Button variant="ghost" :disabled="send.isPending.value" @click="emit('update:chat', null)">
          Отмена
        </Button>
        <Button :disabled="!text.trim() || send.isPending.value" @click="submit">
          <Spinner v-if="send.isPending.value" class="size-4" />
          <Send v-else class="size-4" />
          Отправить
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
