<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  listWebhooksApiWebhooksGet,
  createWebhookApiWebhooksPost,
  deleteWebhookApiWebhooksWebhookIdDelete,
  updateWebhookApiWebhooksWebhookIdPut,
  regenerateWebhookApiKeyApiWebhooksWebhookIdRegeneratePost,
  listChatsApiChatsGet,
} from '@/client'
import type {
  WebhookCreateSchema,
  WebhookUpdateSchema,
  WebhookResponse,
  WebhookListResponse,
  WebhookCreateResponse,
  WebhookRegenerateResponse,
  PaginatedChatsResponse,
  ChatResponse,
} from '@/client'
import { useAuthStore } from '@/stores/auth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
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
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, Trash2, Edit, Copy, RefreshCw, Key, Eye, EyeOff, RotateCw } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const queryClient = useQueryClient()
const authStore = useAuthStore()

// Состояние
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const showApiKeyDialog = ref(false)
const showRegenerateDialog = ref(false)
const selectedWebhook = ref<WebhookResponse | null>(null)
const newApiKey = ref('')
const showApiKey = ref(false)

// Формы
const createForm = ref<WebhookCreateSchema>({
  name: '',
  chat_id: '',
  webhook_metadata: {},
})

const editForm = ref<WebhookUpdateSchema>({
  name: '',
  is_active: true,
  webhook_metadata: {},
})

const metadataJson = ref('{}')
const editMetadataJson = ref('{}')

// Запросы
const { data: webhooksData, isLoading } = useQuery({
  queryKey: ['webhooks'],
  queryFn: async () => {
    const response = await listWebhooksApiWebhooksGet()
    return response.data as WebhookListResponse
  },
})

const { data: chatsData, isLoading: chatsLoading } = useQuery({
  queryKey: ['chats'],
  queryFn: async () => {
    const response = await listChatsApiChatsGet()
    return response.data as PaginatedChatsResponse
  },
})

const webhooks = computed(() => webhooksData.value?.webhooks || [])
const chats = computed(() => chatsData.value?.items || [])

const createMutation = useMutation({
  mutationFn: async (data: WebhookCreateSchema) => {
    const response = await createWebhookApiWebhooksPost({ body: data })
    return response.data as WebhookCreateResponse
  },
  onSuccess: (data) => {
    queryClient.invalidateQueries({ queryKey: ['webhooks'] })
    showCreateDialog.value = false
    newApiKey.value = data.api_key
    showApiKeyDialog.value = true
    resetCreateForm()
    metadataJson.value = '{}'
    toast.success('Вебхук создан', {
      description: 'Вебхук успешно создан. Сохраните API ключ.',
    })
  },
  onError: (error) => {
    toast.error(`Не удалось создать вебхук: ${error.message}`)
  },
})

const updateMutation = useMutation({
  mutationFn: async ({ id, data }: { id: string; data: WebhookUpdateSchema }) => {
    const response = await updateWebhookApiWebhooksWebhookIdPut({ webhookId: id, body: data })
    return response.data as WebhookResponse
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['webhooks'] })
    showEditDialog.value = false
    selectedWebhook.value = null
    editMetadataJson.value = '{}'
    toast.success('Вебхук обновлен', {
      description: 'Вебхук успешно обновлен.',
    })
  },
  onError: (error) => {
    toast.error(`Не удалось обновить вебхук: ${error.message}`)
  },
})

const deleteMutation = useMutation({
  mutationFn: (id: string) => deleteWebhookApiWebhooksWebhookIdDelete({ webhookId: id }),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['webhooks'] })
    showDeleteDialog.value = false
    selectedWebhook.value = null
    toast.success('Вебхук удален', {
      description: 'Вебхук успешно удален.',
    })
  },
  onError: (error) => {
    toast.error(`Не удалось удалить вебхук: ${error.message}`)
  },
})

const regenerateMutation = useMutation({
  mutationFn: async (id: string) => {
    const response = await regenerateWebhookApiKeyApiWebhooksWebhookIdRegeneratePost({ webhookId: id })
    return response.data as WebhookRegenerateResponse
  },
  onSuccess: (data) => {
    newApiKey.value = data.api_key
    showRegenerateDialog.value = false
    showApiKeyDialog.value = true
    toast.success('API ключ перегенерирован', {
      description: 'Новый API ключ сгенерирован. Сохраните его.',
    })
  },
  onError: (error) => {
    toast.error(`Не удалось перегенерировать API ключ: ${error.message}`)
  },
})

// Методы
const resetCreateForm = () => {
  createForm.value = {
    name: '',
    chat_id: '',
    webhook_metadata: {},
  }
}

const parseMetadataJson = (jsonString: string): Record<string, unknown> => {
  try {
    if (!jsonString.trim()) return {}
    const parsed = JSON.parse(jsonString)
    // Ensure it's an object
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error('JSON должен быть объектом')
    }
    return parsed
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Некорректный JSON формат')
    throw error // Re-throw to prevent form submission
  }
}

const openCreateDialog = () => {
  resetCreateForm()
  showCreateDialog.value = true
}

const openEditDialog = (webhook: WebhookResponse) => {
  selectedWebhook.value = webhook
  editForm.value = {
    name: webhook.name,
    is_active: webhook.is_active,
    webhook_metadata: webhook.webhook_metadata,
  }
  editMetadataJson.value = JSON.stringify(webhook.webhook_metadata || {}, null, 2)
  showEditDialog.value = true
}

const openDeleteDialog = (webhook: WebhookResponse) => {
  selectedWebhook.value = webhook
  showDeleteDialog.value = true
}

const openRegenerateDialog = (webhook: WebhookResponse) => {
  selectedWebhook.value = webhook
  showRegenerateDialog.value = true
}

const handleCreate = () => {
  if (!createForm.value.name.trim()) {
    toast.error('Введите название вебхука')
    return
  }
  
  if (!createForm.value.chat_id) {
    toast.error('Выберите чат')
    return
  }
  
  try {
    const formData = {
      ...createForm.value,
      webhook_metadata: parseMetadataJson(metadataJson.value)
    }
    createMutation.mutate(formData)
  } catch (error) {
    // JSON error already handled in parseMetadataJson
  }
}

const handleUpdate = () => {
  if (!selectedWebhook.value) return
  
  if (!editForm.value.name?.trim()) {
    toast.error('Введите название вебхука')
    return
  }
  
  try {
    const formData = {
      ...editForm.value,
      webhook_metadata: parseMetadataJson(editMetadataJson.value)
    }
    updateMutation.mutate({
      id: selectedWebhook.value.id,
      data: formData,
    })
  } catch (error) {
    // JSON error already handled in parseMetadataJson
  }
}

const handleDelete = () => {
  if (!selectedWebhook.value) return
  deleteMutation.mutate(selectedWebhook.value.id)
}

const handleRegenerate = () => {
  if (!selectedWebhook.value) return
  regenerateMutation.mutate(selectedWebhook.value.id)
}

const copyApiKey = () => {
  navigator.clipboard.writeText(newApiKey.value)
  toast.success('API ключ скопирован в буфер обмена.')
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('ru-RU')
}

const getWebhookUrl = (webhookId: string) => {
  return `${window.location.origin}/webhooks/${webhookId}`
}

const copyWebhookUrl = (webhookId: string) => {
  navigator.clipboard.writeText(getWebhookUrl(webhookId))
  toast.success('URL вебхука скопирован в буфер обмена.')
}

const getChatTitle = (chatId: string) => {
  const chat = chats.value.find(c => c.id === chatId)
  return chat?.title || `Чат ${chatId}`
}

const refreshChats = () => {
  queryClient.invalidateQueries({ queryKey: ['chats'] })
}
</script>

<template>
  <div class="container mx-auto py-6">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold">Вебхуки</h1>
        <p class="text-muted-foreground">
          Управление вебхуками для отправки сообщений в чаты из n8n
        </p>
      </div>
      <Button @click="openCreateDialog">
        <Plus class="w-4 h-4 mr-2" />
        Создать вебхук
      </Button>
    </div>

    <!-- Список вебхуков -->
    <Card>
      <CardHeader>
        <CardTitle>Мои вебхуки</CardTitle>
        <CardDescription>
          Все созданные вами вебхуки для интеграции с системами автоматизации
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div v-if="isLoading" class="text-center py-8">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p class="mt-2 text-muted-foreground">Загрузка вебхуков...</p>
        </div>

        <div v-else-if="webhooks.length === 0" class="text-center py-8">
          <p class="text-muted-foreground">У вас еще нет вебхуков</p>
          <Button variant="outline" class="mt-4" @click="openCreateDialog">
            <Plus class="w-4 h-4 mr-2" />
            Создать первый вебхук
          </Button>
        </div>

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>Название</TableHead>
              <TableHead>Чат</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Создан</TableHead>
              <TableHead>Обновлен</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="webhook in webhooks" :key="webhook.id">
              <TableCell class="font-medium">{{ webhook.name }}</TableCell>
               <TableCell>
                 <div class="flex flex-col">
                   <span>{{ getChatTitle(webhook.chat_id) }}</span>
                   <code class="text-xs text-muted-foreground mt-1">{{ webhook.chat_id }}</code>
                 </div>
               </TableCell>
              <TableCell>
                <Badge :variant="webhook.is_active ? 'default' : 'secondary'">
                  {{ webhook.is_active ? 'Активен' : 'Неактивен' }}
                </Badge>
              </TableCell>
              <TableCell>{{ formatDate(webhook.created_at) }}</TableCell>
              <TableCell>{{ formatDate(webhook.updated_at) }}</TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="copyWebhookUrl(webhook.id)"
                    title="Копировать URL вебхука"
                  >
                    <Copy class="w-4 h-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="openRegenerateDialog(webhook)"
                    title="Перегенерировать API ключ"
                  >
                    <RefreshCw class="w-4 h-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="openEditDialog(webhook)"
                    title="Редактировать"
                  >
                    <Edit class="w-4 h-4" />
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    @click="openDeleteDialog(webhook)"
                    title="Удалить"
                  >
                    <Trash2 class="w-4 h-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Диалог создания вебхука -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent class="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Создать вебхук</DialogTitle>
          <DialogDescription>
            Создайте новый вебхук для отправки сообщений в чат
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-4 py-4">
          <div class="grid gap-2">
            <Label for="name">Название вебхука</Label>
            <Input
              id="name"
              v-model="createForm.name"
              placeholder="Например: Уведомления о деплое"
            />
          </div>
          <div class="grid gap-2">
            <div class="flex items-center justify-between">
              <Label for="chat_id">Чат</Label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                @click="refreshChats"
                :disabled="chatsLoading"
                class="h-6 px-2"
              >
                <RotateCw class="w-3 h-3 mr-1" :class="{ 'animate-spin': chatsLoading }" />
                Обновить
              </Button>
            </div>
            <Select v-model="createForm.chat_id" :disabled="chatsLoading">
              <SelectTrigger>
                <SelectValue placeholder="Выберите чат" />
              </SelectTrigger>
              <SelectContent>
                <template v-if="chatsLoading">
                  <SelectItem value="" disabled>Загрузка чатов...</SelectItem>
                </template>
                <template v-else-if="chats.length === 0">
                  <SelectItem value="" disabled>Нет доступных чатов</SelectItem>
                </template>
                <template v-else>
                  <SelectItem v-for="chat in chats" :key="chat.id" :value="chat.id">
                    {{ chat.title || `Чат ${chat.id}` }}
                  </SelectItem>
                </template>
              </SelectContent>
            </Select>
            <p class="text-sm text-muted-foreground">
              Чат, в который будут отправляться сообщения
            </p>
          </div>
          <div class="grid gap-2">
            <Label for="metadata">Дополнительные настройки (JSON)</Label>
            <Textarea
              id="metadata"
              v-model="metadataJson"
              placeholder='{"default_parse_mode": "MarkdownV2", "rate_limit": 10}'
              rows="3"
            />
            <p class="text-sm text-muted-foreground">
              Необязательные настройки в формате JSON
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showCreateDialog = false">Отмена</Button>
          <Button @click="handleCreate" :disabled="createMutation.isPending">
            {{ createMutation.isPending ? 'Создание...' : 'Создать' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Диалог редактирования вебхука -->
    <Dialog v-model:open="showEditDialog">
      <DialogContent class="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Редактировать вебхук</DialogTitle>
          <DialogDescription>Измените настройки вебхука</DialogDescription>
        </DialogHeader>
        <div class="grid gap-4 py-4">
          <div class="grid gap-2">
            <Label for="edit-name">Название вебхука</Label>
            <Input id="edit-name" v-model="editForm.name" />
          </div>
          <div class="grid gap-2">
            <Label for="edit-active">Статус</Label>
            <Select v-model="editForm.is_active">
              <SelectTrigger>
                <SelectValue placeholder="Выберите статус" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem :value="true">Активен</SelectItem>
                <SelectItem :value="false">Неактивен</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid gap-2">
            <Label for="edit-metadata">Дополнительные настройки (JSON)</Label>
            <Textarea
              id="edit-metadata"
              v-model="editMetadataJson"
              rows="3"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showEditDialog = false">Отмена</Button>
          <Button @click="handleUpdate" :disabled="updateMutation.isPending">
            {{ updateMutation.isPending ? 'Сохранение...' : 'Сохранить' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Диалог удаления вебхука -->
    <AlertDialog v-model:open="showDeleteDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить вебхук?</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите удалить вебхук "{{ selectedWebhook?.name }}"?
            Это действие нельзя отменить. Все вызовы этого вебхука прекратятся.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="handleDelete"
            :disabled="deleteMutation.isPending"
            class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {{ deleteMutation.isPending ? 'Удаление...' : 'Удалить' }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <!-- Диалог перегенерации API ключа -->
    <AlertDialog v-model:open="showRegenerateDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Перегенерировать API ключ?</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите перегенерировать API ключ для вебхука "{{ selectedWebhook?.name }}"?
            Старый ключ перестанет работать. Все интеграции с этим ключом нужно будет обновить.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="handleRegenerate"
            :disabled="regenerateMutation.isPending"
          >
            {{ regenerateMutation.isPending ? 'Перегенерация...' : 'Перегенерировать' }}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <!-- Диалог отображения API ключа -->
    <Dialog v-model:open="showApiKeyDialog">
      <DialogContent class="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            <Key class="w-5 h-5 inline mr-2" />
            API ключ
          </DialogTitle>
          <DialogDescription>
            Сохраните этот ключ! Он показывается только один раз.
          </DialogDescription>
        </DialogHeader>
        <div class="py-4">
          <div class="relative">
            <Input
              :type="showApiKey ? 'text' : 'password'"
              :value="newApiKey"
              readonly
              class="pr-10 font-mono"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              class="absolute right-0 top-0 h-full px-3"
              @click="showApiKey = !showApiKey"
            >
              <Eye v-if="!showApiKey" class="w-4 h-4" />
              <EyeOff v-else class="w-4 h-4" />
            </Button>
          </div>
          <div class="mt-4 p-3 bg-muted rounded-md">
            <p class="text-sm font-medium mb-1">Как использовать:</p>
            <ul class="text-sm text-muted-foreground space-y-1">
              <li>• Добавьте заголовок: <code class="bg-background px-1 rounded">Authorization: Bearer {ключ}</code></li>
              <li>• Отправляйте POST запросы на: <code class="bg-background px-1 rounded">{{ getWebhookUrl(selectedWebhook?.id || '') }}</code></li>
              <li>• Формат тела: JSON с полями <code class="bg-background px-1 rounded">text</code>, <code class="bg-background px-1 rounded">parse_mode</code></li>
            </ul>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="copyApiKey">
            <Copy class="w-4 h-4 mr-2" />
            Копировать
          </Button>
          <Button @click="showApiKeyDialog = false">Закрыть</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>