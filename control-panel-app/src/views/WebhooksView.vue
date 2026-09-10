<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useClipboard } from '@vueuse/core'
import {
  Check,
  Copy,
  KeyRound,
  Link2,
  Pencil,
  Plus,
  Power,
  Trash2,
  Webhook as WebhookIcon,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { WebhookResponse } from '@/client'
import {
  createWebhookApiWebhooksPostMutation,
  deleteWebhookApiWebhooksWebhookIdDeleteMutation,
  listChatsApiChatsGetOptions,
  listWebhooksApiWebhooksGetOptions,
  listWebhooksApiWebhooksGetQueryKey,
  regenerateWebhookApiKeyApiWebhooksWebhookIdRegeneratePostMutation,
  updateWebhookApiWebhooksWebhookIdPutMutation,
} from '@/client/@tanstack/vue-query.gen'
import { API_BASE_URL } from '@/hey-api'
import PageHeader from '@/components/layout/PageHeader.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import RowActions from '@/components/data/RowActions.vue'
import WebhookFormDialog from '@/components/WebhookFormDialog.vue'
import WebhookKeyDialog from '@/components/WebhookKeyDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem, DropdownMenuSeparator } from '@/components/ui/dropdown-menu'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { formatRelative } from '@/lib/format'

const queryClient = useQueryClient()
const { copy, copied } = useClipboard({ legacy: true })

/** `null` — закрыто, объект без id — создание, с id — редактирование. */
const editing = ref<Partial<WebhookResponse> | null>(null)
const toDelete = ref<WebhookResponse | null>(null)
const toRegenerate = ref<WebhookResponse | null>(null)
const issuedKey = ref<{ webhook: WebhookResponse; apiKey: string } | null>(null)

const { data, isPending, isError, refetch } = useQuery(listWebhooksApiWebhooksGetOptions())
const { data: chatsData } = useQuery(
  listChatsApiChatsGetOptions({ query: { page: 1, size: 200 } }),
)

const webhooks = computed(() => data.value?.webhooks ?? [])
const chats = computed(() => chatsData.value?.items ?? [])

function chatTitle(chatId: string) {
  return chats.value.find((chat) => chat.id === chatId)?.title || chatId
}

function webhookUrl(id: string) {
  return `${API_BASE_URL}/webhooks/${id}`
}

function invalidate() {
  queryClient.invalidateQueries({ queryKey: listWebhooksApiWebhooksGetQueryKey() })
}

const createWebhook = useMutation({
  ...createWebhookApiWebhooksPostMutation(),
  onSuccess: (created) => {
    invalidate()
    editing.value = null
    issuedKey.value = { webhook: created.webhook, apiKey: created.api_key }
  },
  onError: () => toast.error('Не удалось создать вебхук'),
})

const updateWebhook = useMutation({
  ...updateWebhookApiWebhooksWebhookIdPutMutation(),
  onSuccess: () => {
    invalidate()
    editing.value = null
    toast.success('Вебхук сохранён')
  },
  onError: () => toast.error('Не удалось сохранить вебхук'),
})

const deleteWebhook = useMutation({
  ...deleteWebhookApiWebhooksWebhookIdDeleteMutation(),
  onSuccess: () => {
    invalidate()
    toast.success(`Вебхук «${toDelete.value?.name}» удалён`)
    toDelete.value = null
  },
  onError: () => toast.error('Не удалось удалить вебхук'),
})

const regenerate = useMutation({
  ...regenerateWebhookApiKeyApiWebhooksWebhookIdRegeneratePostMutation(),
  onSuccess: (result) => {
    invalidate()
    if (toRegenerate.value) {
      issuedKey.value = { webhook: toRegenerate.value, apiKey: result.api_key }
    }
    toRegenerate.value = null
  },
  onError: () => toast.error('Не удалось выпустить новый ключ'),
})

function submit(form: { name: string; chatId: string; metadata: Record<string, unknown> }) {
  const webhook = editing.value
  if (!webhook) return
  if (webhook.id) {
    updateWebhook.mutate({
      path: { webhook_id: webhook.id },
      body: {
        name: form.name,
        is_active: webhook.is_active ?? true,
        webhook_metadata: form.metadata,
      },
    })
  } else {
    createWebhook.mutate({
      body: { name: form.name, chat_id: form.chatId, webhook_metadata: form.metadata },
    })
  }
}

function toggleActive(webhook: WebhookResponse) {
  updateWebhook.mutate({
    path: { webhook_id: webhook.id },
    body: {
      name: webhook.name,
      is_active: !webhook.is_active,
      webhook_metadata: webhook.webhook_metadata,
    },
  })
}
</script>

<template>
  <div>
    <PageHeader>
      <template #actions>
        <Button size="sm" :disabled="!chats.length" @click="editing = {}">
          <Plus class="size-4" />
          Новый вебхук
        </Button>
      </template>
    </PageHeader>

    <DataTableShell
      :loading="isPending"
      :error="isError ? true : undefined"
      :empty="!webhooks.length"
      :columns="4"
      :empty-icon="WebhookIcon"
      empty-title="Вебхуков пока нет"
      empty-description="Вебхук даёт внешней системе адрес и ключ, по которым она отправляет сообщение в чат."
      @retry="refetch()"
    >
      <template #empty-action>
        <Button :disabled="!chats.length" @click="editing = {}">
          <Plus class="size-4" />
          Новый вебхук
        </Button>
      </template>

      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead>Вебхук</TableHead>
            <TableHead>Чат</TableHead>
            <TableHead class="w-40">Состояние</TableHead>
            <TableHead class="w-16 text-right">
              <span class="sr-only">Действия</span>
            </TableHead>
          </TableRow>
        </TableHeader>
      </template>

      <template #body>
        <TableBody>
          <TableRow v-for="webhook in webhooks" :key="webhook.id">
            <TableCell>
              <div class="font-medium">{{ webhook.name }}</div>
              <button
                type="button"
                class="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                @click="copy(webhookUrl(webhook.id))"
              >
                <Check v-if="copied" class="size-3" />
                <Link2 v-else class="size-3" />
                /webhooks/{{ webhook.id }}
              </button>
            </TableCell>
            <TableCell>{{ chatTitle(webhook.chat_id) }}</TableCell>
            <TableCell>
              <Badge v-if="webhook.is_active" variant="secondary">Активен</Badge>
              <Badge v-else variant="outline">Выключен</Badge>
              <div class="mt-1 text-xs text-muted-foreground">
                создан {{ formatRelative(webhook.created_at) }}
              </div>
            </TableCell>
            <TableCell class="text-right">
              <RowActions>
                <DropdownMenuItem @click="copy(webhookUrl(webhook.id))">
                  <Copy />
                  Скопировать адрес
                </DropdownMenuItem>
                <DropdownMenuItem @click="editing = webhook">
                  <Pencil />
                  Изменить
                </DropdownMenuItem>
                <DropdownMenuItem @click="toggleActive(webhook)">
                  <Power />
                  {{ webhook.is_active ? 'Выключить' : 'Включить' }}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem @click="toRegenerate = webhook">
                  <KeyRound />
                  Новый ключ
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" @click="toDelete = webhook">
                  <Trash2 />
                  Удалить
                </DropdownMenuItem>
              </RowActions>
            </TableCell>
          </TableRow>
        </TableBody>
      </template>
    </DataTableShell>

    <WebhookFormDialog
      :webhook="editing"
      :chats="chats"
      :pending="createWebhook.isPending.value || updateWebhook.isPending.value"
      @submit="submit"
      @close="editing = null"
    />

    <WebhookKeyDialog
      :issued="issuedKey"
      :url="issuedKey ? webhookUrl(issuedKey.webhook.id) : ''"
      @close="issuedKey = null"
    />

    <AlertDialog :open="toDelete !== null" @update:open="toDelete = null">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить вебхук «{{ toDelete?.name }}»?</AlertDialogTitle>
          <AlertDialogDescription>
            Адрес перестанет отвечать, и запросы внешней системы начнут падать.
            Отменить нельзя.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="toDelete && deleteWebhook.mutate({ path: { webhook_id: toDelete.id } })"
          >
            Удалить вебхук
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <AlertDialog :open="toRegenerate !== null" @update:open="toRegenerate = null">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Выпустить новый ключ?</AlertDialogTitle>
          <AlertDialogDescription>
            Старый ключ «{{ toRegenerate?.name }}» перестанет работать сразу же —
            замените его в системе, которая вызывает вебхук.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="
              toRegenerate && regenerate.mutate({ path: { webhook_id: toRegenerate.id } })
            "
          >
            Выпустить ключ
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
