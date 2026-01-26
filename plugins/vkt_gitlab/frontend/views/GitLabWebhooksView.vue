<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  listWebhooksApiGlWebhooksGet,
  deleteWebhookApiGlWebhooksWebhookIdDelete,
  createWebhookApiGlWebhooksPost,
  updateWebhookApiGlWebhooksWebhookIdPatch,
} from '@/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog'
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
import { Label } from '@/components/ui/label'
import { Search, Plus, Trash2, Edit, Copy, ExternalLink } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const queryClient = useQueryClient()

const page = ref(1)
const size = ref(10)
const searchQuery = ref('')

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const selectedWebhook = ref<any>(null)

const newWebhook = ref({
  name: '',
  secret: '',
  chat_id: '',
})

const editWebhook = ref({
  name: '',
})

const { data: webhooksData, isLoading } = useQuery({
  queryKey: ['gitlab-webhooks', page, size],
  queryFn: async () => {
    const response = await listWebhooksApiGlWebhooksGet({
      query: { page: page.value, size: size.value },
    })
    return response.data
  },
})

const filteredWebhooks = computed(() => {
  if (!webhooksData.value?.items) return []
  if (!searchQuery.value) return webhooksData.value.items

  const query = searchQuery.value.toLowerCase()
  return webhooksData.value.items.filter(
    (webhook: any) =>
      webhook.name?.toLowerCase().includes(query) ||
      webhook.chat_title?.toLowerCase().includes(query),
  )
})

const createMutation = useMutation({
  mutationFn: async () => {
    const response = await createWebhookApiGlWebhooksPost({
      body: {
        name: newWebhook.value.name,
        secret: newWebhook.value.secret,
        chat_id: newWebhook.value.chat_id,
      },
    })
    return response.data
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['gitlab-webhooks'] })
    showCreateDialog.value = false
    newWebhook.value = { name: '', secret: '', chat_id: '' }
    toast.success('Webhook создан успешно')
  },
  onError: (error: any) => {
    toast.error(error.message || 'Не удалось создать webhook')
  },
})

const updateMutation = useMutation({
  mutationFn: async () => {
    const response = await updateWebhookApiGlWebhooksWebhookIdPatch({
      path: { webhook_id: selectedWebhook.value.id },
      body: { name: editWebhook.value.name },
    })
    return response.data
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['gitlab-webhooks'] })
    showEditDialog.value = false
    selectedWebhook.value = null
    toast.success('Webhook обновлен успешно')
  },
  onError: (error: any) => {
    toast.error(error.message || 'Не удалось обновить webhook')
  },
})

const deleteMutation = useMutation({
  mutationFn: async (webhookId: string) => {
    await deleteWebhookApiGlWebhooksWebhookIdDelete({
      path: { webhook_id: webhookId },
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['gitlab-webhooks'] })
    showDeleteDialog.value = false
    selectedWebhook.value = null
    toast.success('Webhook удален успешно')
  },
  onError: (error: any) => {
    toast.error(error.message || 'Не удалось удалить webhook')
  },
})

function openCreateDialog() {
  newWebhook.value = { name: '', secret: '', chat_id: '' }
  showCreateDialog.value = true
}

function openEditDialog(webhook: any) {
  selectedWebhook.value = webhook
  editWebhook.value = { name: webhook.name }
  showEditDialog.value = true
}

function openDeleteDialog(webhook: any) {
  selectedWebhook.value = webhook
  showDeleteDialog.value = true
}

function copyWebhookUrl(webhookId: string) {
  const url = `${window.location.origin}/api/gl/webhooks/${webhookId}/trigger`
  navigator.clipboard.writeText(url)
  toast.success('URL webhook скопирован в буфер обмена')
}

function formatDate(dateString: string | null) {
  if (!dateString) return '—'
  return new Date(dateString).toLocaleString('ru-RU')
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="relative flex-1 max-w-sm">
        <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input v-model="searchQuery" placeholder="Поиск по названию или чату..." class="pl-9" />
      </div>
      <Button @click="openCreateDialog">
        <Plus class="mr-2 h-4 w-4" />
        Создать webhook
      </Button>
    </div>

    <Card>
      <CardContent class="pt-6">
        <Table v-if="!isLoading && webhooksData">
          <TableHeader>
            <TableRow>
              <TableHead>Название</TableHead>
              <TableHead>Чат</TableHead>
              <TableHead>Создал</TableHead>
              <TableHead>Последнее использование</TableHead>
              <TableHead>Создан</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="webhook in filteredWebhooks" :key="webhook.id">
              <TableCell class="font-medium">{{ webhook.name || '—' }}</TableCell>
              <TableCell>{{ webhook.chat_title || webhook.chat_id }}</TableCell>
              <TableCell>{{ webhook.created_by_name || '—' }}</TableCell>
              <TableCell>{{ formatDate(webhook.last_used_at) }}</TableCell>
              <TableCell>{{ formatDate(webhook.created_at) }}</TableCell>
              <TableCell class="text-right">
                <div class="flex items-center justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    @click="copyWebhookUrl(webhook.id)"
                    title="Скопировать URL"
                  >
                    <Copy class="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    @click="openEditDialog(webhook)"
                    title="Редактировать"
                  >
                    <Edit class="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    @click="openDeleteDialog(webhook)"
                    title="Удалить"
                  >
                    <Trash2 class="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div v-else class="py-8 text-center">Загрузка...</div>
      </CardContent>
    </Card>

    <div v-if="webhooksData" class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Показано {{ filteredWebhooks.length }} из {{ webhooksData.total }} webhooks
      </div>
      <div class="flex gap-2">
        <Button variant="outline" :disabled="page <= 1" @click="page--">Назад</Button>
        <Button variant="outline" :disabled="page >= webhooksData.pages" @click="page++">
          Далее
        </Button>
      </div>
    </div>

    <!-- Create Dialog -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Создать GitLab Webhook</DialogTitle>
          <DialogDescription>
            Создайте новый webhook для получения уведомлений от GitLab
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-2">
            <Label for="name">Название</Label>
            <Input id="name" v-model="newWebhook.name" placeholder="Мой проект" />
          </div>
          <div class="space-y-2">
            <Label for="secret">Секретный токен</Label>
            <Input
              id="secret"
              v-model="newWebhook.secret"
              type="password"
              placeholder="Введите секретный токен"
            />
          </div>
          <div class="space-y-2">
            <Label for="chat_id">ID чата</Label>
            <Input id="chat_id" v-model="newWebhook.chat_id" placeholder="chat@conference..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showCreateDialog = false">Отмена</Button>
          <Button @click="createMutation.mutate()" :disabled="createMutation.isPending.value">
            {{ createMutation.isPending.value ? 'Создание...' : 'Создать' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Edit Dialog -->
    <Dialog v-model:open="showEditDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Редактировать webhook</DialogTitle>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-2">
            <Label for="edit-name">Название</Label>
            <Input id="edit-name" v-model="editWebhook.name" placeholder="Мой проект" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showEditDialog = false">Отмена</Button>
          <Button @click="updateMutation.mutate()" :disabled="updateMutation.isPending.value">
            {{ updateMutation.isPending.value ? 'Сохранение...' : 'Сохранить' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete Dialog -->
    <AlertDialog v-model:open="showDeleteDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить webhook?</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите удалить webhook "{{ selectedWebhook?.name }}"? Это действие
            нельзя отменить.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="deleteMutation.mutate(selectedWebhook.id)"
            :disabled="deleteMutation.isPending.value"
          >
            {{ deleteMutation.isPending.value ? 'Удаление...' : 'Удалить' }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
