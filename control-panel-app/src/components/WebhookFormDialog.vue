<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChatResponse, WebhookResponse } from '@/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'

/** Один диалог на создание и правку. Чат после создания менять нельзя. */
const props = defineProps<{
  webhook: Partial<WebhookResponse> | null
  chats: ChatResponse[]
  pending?: boolean
}>()

const emit = defineEmits<{
  submit: [{ name: string; chatId: string; metadata: Record<string, unknown> }]
  close: []
}>()

const name = ref('')
const chatId = ref('')
const metadata = ref('{}')

watch(
  () => props.webhook,
  (webhook) => {
    if (!webhook) return
    name.value = webhook.name ?? ''
    chatId.value = webhook.chat_id ?? ''
    metadata.value = JSON.stringify(webhook.webhook_metadata ?? {}, null, 2)
  },
  { immediate: true },
)

const isEdit = computed(() => Boolean(props.webhook?.id))

/** Пустое поле — это `{}`; сообщение об ошибке показываем сразу под полем. */
const parsed = computed<{ value: Record<string, unknown> } | { error: string }>(() => {
  const raw = metadata.value.trim()
  if (!raw) return { value: {} }
  try {
    const value = JSON.parse(raw)
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      return { error: 'Нужен объект в фигурных скобках' }
    }
    return { value: value as Record<string, unknown> }
  } catch {
    return { error: 'Это не похоже на JSON' }
  }
})

const error = computed(() => ('error' in parsed.value ? parsed.value.error : null))
const canSubmit = computed(
  () => Boolean(name.value.trim()) && Boolean(chatId.value) && !error.value && !props.pending,
)

function submit() {
  if (!canSubmit.value || 'error' in parsed.value) return
  emit('submit', {
    name: name.value.trim(),
    chatId: chatId.value,
    metadata: parsed.value.value,
  })
}
</script>

<template>
  <Dialog :open="webhook !== null" @update:open="emit('close')">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ isEdit ? 'Изменить вебхук' : 'Новый вебхук' }}</DialogTitle>
        <DialogDescription>
          Внешняя система получит адрес и ключ, по которым сможет писать в чат.
        </DialogDescription>
      </DialogHeader>

      <form class="space-y-4" @submit.prevent="submit">
        <div class="space-y-2">
          <Label for="webhook-name">Название</Label>
          <Input
            id="webhook-name"
            v-model="name"
            autofocus
            placeholder="Уведомления о деплое"
            :disabled="pending"
          />
        </div>

        <div class="space-y-2">
          <Label for="webhook-chat">Чат</Label>
          <Select v-model="chatId" :disabled="isEdit || pending">
            <SelectTrigger id="webhook-chat">
              <SelectValue placeholder="Куда отправлять" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="chat in chats" :key="chat.id" :value="chat.id">
                {{ chat.title || chat.id }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-if="isEdit" class="text-xs text-muted-foreground">
            Чат у существующего вебхука не меняется — создайте новый.
          </p>
        </div>

        <Collapsible>
          <CollapsibleTrigger as-child>
            <Button type="button" variant="ghost" size="sm" class="text-muted-foreground">
              Дополнительные параметры
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent class="space-y-2 pt-2">
            <Label for="webhook-metadata">Параметры (JSON)</Label>
            <Textarea
              id="webhook-metadata"
              v-model="metadata"
              rows="4"
              class="font-mono text-sm"
              placeholder='{"default_parse_mode": "MarkdownV2"}'
              :disabled="pending"
              :aria-invalid="Boolean(error)"
            />
            <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
          </CollapsibleContent>
        </Collapsible>
      </form>

      <DialogFooter>
        <Button variant="ghost" :disabled="pending" @click="emit('close')">Отмена</Button>
        <Button :disabled="!canSubmit" @click="submit">
          <Spinner v-if="pending" class="size-4" />
          {{ isEdit ? 'Сохранить' : 'Создать вебхук' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
