<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { useClipboard } from '@vueuse/core'
import { Check, Copy, GitBranch, Link2, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { GlWebhookRead } from '@/client'
import {
  createWebhookGlWebhooksPostMutation,
  deleteWebhookGlWebhooksWebhookIdDeleteMutation,
  listChatsApiChatsGetOptions,
  listWebhooksGlWebhooksGetOptions,
  listWebhooksGlWebhooksGetQueryKey,
  updateWebhookGlWebhooksWebhookIdPatchMutation,
} from '@/client/@tanstack/vue-query.gen'
import { API_BASE_URL } from '@/hey-api'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import DataToolbar from '@/components/data/DataToolbar.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import RowActions from '@/components/data/RowActions.vue'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem, DropdownMenuSeparator } from '@/components/ui/dropdown-menu'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
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
import { useListQuery } from '@/composables/useListQuery'
import { formatRelative } from '@/lib/format'

const queryClient = useQueryClient()
const { copy, copied } = useClipboard({ legacy: true })
const { page, pageSize, searchInput, search } = useListQuery()

const creating = ref(false)
const renaming = ref<GlWebhookRead | null>(null)
const toDelete = ref<GlWebhookRead | null>(null)

const form = ref({ name: '', secret: '', chatId: '' })
const newName = ref('')

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listWebhooksGlWebhooksGetOptions({ query: { page: page.value, size: pageSize.value } }),
  ),
)

const { data: chatsData } = useQuery(
  listChatsApiChatsGetOptions({ query: { page: 1, size: 200 } }),
)

const chats = computed(() => chatsData.value?.items ?? [])

/** У ручки списка нет поиска, поэтому фильтруем загруженную страницу. */
const rows = computed(() => {
  const items = data.value?.items ?? []
  const query = search.value.trim().toLowerCase()
  if (!query) return items
  return items.filter(
    (webhook) =>
      webhook.name?.toLowerCase().includes(query) ||
      webhook.chat_title?.toLowerCase().includes(query),
  )
})

function triggerUrl(id: string) {
  return `${API_BASE_URL}/gl/webhooks/${id}/trigger`
}

function invalidate() {
  queryClient.invalidateQueries({ queryKey: listWebhooksGlWebhooksGetQueryKey() })
}

const createWebhook = useMutation({
  ...createWebhookGlWebhooksPostMutation(),
  onSuccess: (created) => {
    invalidate()
    creating.value = false
    form.value = { name: '', secret: '', chatId: '' }
    copy(triggerUrl(created.id))
    toast.success('Вебхук создан, адрес скопирован', {
      description: 'Вставьте его в настройки проекта GitLab.',
    })
  },
  onError: () => toast.error('Не удалось создать вебхук'),
})

const renameWebhook = useMutation({
  ...updateWebhookGlWebhooksWebhookIdPatchMutation(),
  onSuccess: () => {
    invalidate()
    renaming.value = null
    toast.success('Название сохранено')
  },
  onError: () => toast.error('Не удалось сохранить название'),
})

const deleteWebhook = useMutation({
  ...deleteWebhookGlWebhooksWebhookIdDeleteMutation(),
  onSuccess: () => {
    invalidate()
    toast.success('Вебхук удалён')
    toDelete.value = null
  },
  onError: () => toast.error('Не удалось удалить вебхук'),
})

function openRename(webhook: GlWebhookRead) {
  renaming.value = webhook
  newName.value = webhook.name ?? ''
}
</script>

<template>
  <div class="space-y-8">
    <PageHeader>
      <template #actions>
        <Button size="sm" :disabled="!chats.length" @click="creating = true">
          <Plus class="size-4" />
          Новый вебхук
        </Button>
      </template>
    </PageHeader>

    <div>
      <DataToolbar v-model:search="searchInput" placeholder="Название или чат" />

      <DataTableShell
        :loading="isPending"
        :error="isError ? true : undefined"
        :empty="!rows.length"
        :columns="4"
        :empty-icon="GitBranch"
        :empty-title="search ? 'Вебхук не нашёлся' : 'Вебхуков GitLab пока нет'"
        :empty-description="
          search
            ? 'Проверьте название или имя чата.'
            : 'Вебхук даёт GitLab адрес, по которому он сообщает о пайплайнах в чат.'
        "
        @retry="refetch()"
      >
        <template #empty-action>
          <Button v-if="!search" :disabled="!chats.length" @click="creating = true">
            <Plus class="size-4" />
            Новый вебхук
          </Button>
        </template>

        <template #header>
          <TableHeader>
            <TableRow>
              <TableHead>Вебхук</TableHead>
              <TableHead>Чат</TableHead>
              <TableHead class="w-44">Последний вызов</TableHead>
              <TableHead class="w-16 text-right">
                <span class="sr-only">Действия</span>
              </TableHead>
            </TableRow>
          </TableHeader>
        </template>

        <template #body>
          <TableBody>
            <TableRow v-for="webhook in rows" :key="webhook.id">
              <TableCell>
                <div class="font-medium">{{ webhook.name || 'Без названия' }}</div>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                  @click="copy(triggerUrl(webhook.id))"
                >
                  <Check v-if="copied" class="size-3" />
                  <Link2 v-else class="size-3" />
                  /gl/webhooks/{{ webhook.id }}/trigger
                </button>
              </TableCell>
              <TableCell>{{ webhook.chat_title || webhook.chat_id }}</TableCell>
              <TableCell class="text-muted-foreground">
                {{ webhook.last_used_at ? formatRelative(webhook.last_used_at) : 'ещё не звали' }}
              </TableCell>
              <TableCell class="text-right">
                <RowActions>
                  <DropdownMenuItem @click="copy(triggerUrl(webhook.id))">
                    <Copy />
                    Скопировать адрес
                  </DropdownMenuItem>
                  <DropdownMenuItem @click="openRename(webhook)">
                    <Pencil />
                    Переименовать
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
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

      <TablePagination
        v-if="data"
        :page="page"
        :size="pageSize"
        :total="data.total"
        :pages="data.pages"
        items-label="вебхуков"
        @update:page="page = $event"
      />
    </div>

    <PageSection title="Как подключить">
      <ol class="ml-4 list-decimal space-y-1.5 text-sm text-muted-foreground">
        <li>Создайте здесь вебхук и выберите чат — адрес скопируется сам.</li>
        <li>
          В GitLab откройте Settings → Webhooks, вставьте адрес и тот же секретный
          токен в поле Secret token.
        </li>
        <li>Включите триггер Pipeline events и сохраните.</li>
      </ol>
    </PageSection>

    <Dialog v-model:open="creating">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Новый вебхук GitLab</DialogTitle>
          <DialogDescription>
            Секретный токен придумываете вы — его же нужно вписать в GitLab.
          </DialogDescription>
        </DialogHeader>

        <form class="space-y-4" @submit.prevent>
          <div class="space-y-2">
            <Label for="gl-name">Название</Label>
            <Input
              id="gl-name"
              v-model="form.name"
              autofocus
              placeholder="backend / main"
              :disabled="createWebhook.isPending.value"
            />
          </div>
          <div class="space-y-2">
            <Label for="gl-chat">Чат</Label>
            <Select v-model="form.chatId" :disabled="createWebhook.isPending.value">
              <SelectTrigger id="gl-chat">
                <SelectValue placeholder="Куда писать о пайплайнах" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="chat in chats" :key="chat.id" :value="chat.id">
                  {{ chat.title || chat.id }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-2">
            <Label for="gl-secret">Секретный токен</Label>
            <Input
              id="gl-secret"
              v-model="form.secret"
              class="font-mono"
              placeholder="строка, которую вы вставите в GitLab"
              :disabled="createWebhook.isPending.value"
            />
          </div>
        </form>

        <DialogFooter>
          <Button
            variant="ghost"
            :disabled="createWebhook.isPending.value"
            @click="creating = false"
          >
            Отмена
          </Button>
          <Button
            :disabled="
              !form.secret.trim() || !form.chatId || createWebhook.isPending.value
            "
            @click="
              createWebhook.mutate({
                body: {
                  name: form.name.trim() || undefined,
                  secret: form.secret.trim(),
                  chat_id: form.chatId,
                },
              })
            "
          >
            <Spinner v-if="createWebhook.isPending.value" class="size-4" />
            Создать вебхук
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog :open="renaming !== null" @update:open="renaming = null">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Переименовать вебхук</DialogTitle>
          <DialogDescription>
            Название видно только в панели — в GitLab оно не передаётся.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <Label for="gl-new-name">Название</Label>
          <Input id="gl-new-name" v-model="newName" autofocus />
        </div>
        <DialogFooter>
          <Button variant="ghost" @click="renaming = null">Отмена</Button>
          <Button
            :disabled="renameWebhook.isPending.value"
            @click="
              renaming &&
                renameWebhook.mutate({
                  path: { webhook_id: renaming.id },
                  body: { name: newName.trim() },
                })
            "
          >
            <Spinner v-if="renameWebhook.isPending.value" class="size-4" />
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <AlertDialog :open="toDelete !== null" @update:open="toDelete = null">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Удалить вебхук «{{ toDelete?.name || toDelete?.id }}»?
          </AlertDialogTitle>
          <AlertDialogDescription>
            GitLab начнёт получать ошибку на этот адрес, а уведомления о пайплайнах
            в чат перестанут приходить.
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
  </div>
</template>
