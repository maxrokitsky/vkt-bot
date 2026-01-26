<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import {
  listLogsApiLogsGet,
  type ActionType,
  type ActorType,
  type EntityType,
} from '@/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Search, X } from 'lucide-vue-next'

const page = ref(1)
const size = ref(20)

// Фильтры
const actorTypeFilter = ref<ActorType | undefined>(undefined)
const actorIdFilter = ref<string | undefined>(undefined)
const actionTypeFilter = ref<ActionType | undefined>(undefined)
const entityTypeFilter = ref<EntityType | undefined>(undefined)
const entityIdFilter = ref<string | undefined>(undefined)
const searchQuery = ref<string | undefined>(undefined)

const { data: logsData, isLoading } = useQuery({
  queryKey: [
    'logs',
    page,
    size,
    actorTypeFilter,
    actorIdFilter,
    actionTypeFilter,
    entityTypeFilter,
    entityIdFilter,
    searchQuery,
  ],
  queryFn: async () => {
    const response = await listLogsApiLogsGet({
      query: {
        page: page.value,
        size: size.value,
        actor_type: actorTypeFilter.value,
        actor_id: actorIdFilter.value,
        action_type: actionTypeFilter.value,
        entity_type: entityTypeFilter.value,
        entity_id: entityIdFilter.value,
        search_query: searchQuery.value,
      },
    })
    return response.data
  },
})

const totalPages = computed(() => logsData.value?.pages || 0)

function nextPage() {
  if (page.value < totalPages.value) {
    page.value++
  }
}

function prevPage() {
  if (page.value > 1) {
    page.value--
  }
}

function clearFilters() {
  actorTypeFilter.value = undefined
  actorIdFilter.value = undefined
  actionTypeFilter.value = undefined
  entityTypeFilter.value = undefined
  entityIdFilter.value = undefined
  searchQuery.value = undefined
  page.value = 1
}

function formatTimestamp(timestamp: string) {
  return new Date(timestamp).toLocaleString('ru-RU')
}

function getActionBadgeVariant(actionType: ActionType): 'default' | 'destructive' | 'outline' | 'secondary' {
  switch (actionType) {
    case 'create':
      return 'default'
    case 'update':
      return 'secondary'
    case 'delete':
      return 'destructive'
    case 'assign':
    case 'unassign':
      return 'outline'
    default:
      return 'default'
  }
}

function getActorBadgeVariant(actorType: ActorType): 'default' | 'destructive' | 'outline' | 'secondary' {
  switch (actorType) {
    case 'web_user':
      return 'default'
    case 'bot_user':
      return 'secondary'
    case 'system':
      return 'outline'
    default:
      return 'default'
  }
}

const actorTypeLabels: Record<ActorType, string> = {
  web_user: 'Веб-пользователь',
  bot_user: 'Пользователь бота',
  system: 'Система',
}

const actionTypeLabels: Record<ActionType, string> = {
  create: 'Создание',
  update: 'Обновление',
  delete: 'Удаление',
  assign: 'Назначение',
  unassign: 'Снятие',
}

const entityTypeLabels: Record<EntityType, string> = {
  user: 'Пользователь',
  chat_user: 'Пользователь чата',
  role: 'Роль',
  chat: 'Чат',
  role_assignment: 'Назначение роли',
  chat_membership: 'Членство в чате',
  bot_settings: 'Настройки бота',
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-3xl font-bold">Логи аудита</h1>
        <p class="text-muted-foreground">История действий в системе</p>
      </div>
    </div>

    <!-- Фильтры -->
    <div class="bg-card border rounded-lg p-4 space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold">Фильтры</h3>
        <Button variant="ghost" size="sm" @click="clearFilters">
          <X class="h-4 w-4 mr-2" />
          Очистить
        </Button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="space-y-2">
          <Label>Тип актора</Label>
          <Select v-model="actorTypeFilter">
            <SelectTrigger>
              <SelectValue placeholder="Все типы" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="undefined">Все типы</SelectItem>
              <SelectItem value="web_user">Веб-пользователь</SelectItem>
              <SelectItem value="bot_user">Пользователь бота</SelectItem>
              <SelectItem value="system">Система</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="space-y-2">
          <Label>Тип действия</Label>
          <Select v-model="actionTypeFilter">
            <SelectTrigger>
              <SelectValue placeholder="Все действия" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="undefined">Все действия</SelectItem>
              <SelectItem value="create">Создание</SelectItem>
              <SelectItem value="update">Обновление</SelectItem>
              <SelectItem value="delete">Удаление</SelectItem>
              <SelectItem value="assign">Назначение</SelectItem>
              <SelectItem value="unassign">Снятие</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="space-y-2">
          <Label>Тип сущности</Label>
          <Select v-model="entityTypeFilter">
            <SelectTrigger>
              <SelectValue placeholder="Все сущности" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="undefined">Все сущности</SelectItem>
              <SelectItem value="user">Пользователь</SelectItem>
              <SelectItem value="chat_user">Пользователь чата</SelectItem>
              <SelectItem value="role">Роль</SelectItem>
              <SelectItem value="chat">Чат</SelectItem>
              <SelectItem value="role_assignment">Назначение роли</SelectItem>
              <SelectItem value="chat_membership">Членство в чате</SelectItem>
              <SelectItem value="bot_settings">Настройки бота</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="space-y-2">
          <Label>ID актора</Label>
          <Input v-model="actorIdFilter" placeholder="Введите ID" />
        </div>

        <div class="space-y-2">
          <Label>ID сущности</Label>
          <Input v-model="entityIdFilter" placeholder="Введите ID" />
        </div>

        <div class="space-y-2">
          <Label>Поиск по описанию</Label>
          <div class="relative">
            <Search class="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input v-model="searchQuery" placeholder="Поиск..." class="pl-8" />
          </div>
        </div>
      </div>
    </div>

    <!-- Таблица логов -->
    <div class="border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Время</TableHead>
            <TableHead>Актор</TableHead>
            <TableHead>Действие</TableHead>
            <TableHead>Сущность</TableHead>
            <TableHead>Описание</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="5" class="text-center py-8 text-muted-foreground">
              Загрузка...
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!logsData?.items.length">
            <TableCell colspan="5" class="text-center py-8 text-muted-foreground">
              Нет логов
            </TableCell>
          </TableRow>
          <TableRow v-for="log in logsData?.items" :key="log.id">
            <TableCell class="whitespace-nowrap">
              {{ formatTimestamp(log.timestamp) }}
            </TableCell>
            <TableCell>
              <div class="space-y-1">
                <Badge :variant="getActorBadgeVariant(log.actor_type)">
                  {{ actorTypeLabels[log.actor_type] }}
                </Badge>
                <div v-if="log.actor_id" class="text-xs text-muted-foreground">
                  {{ log.actor_id }}
                </div>
              </div>
            </TableCell>
            <TableCell>
              <Badge :variant="getActionBadgeVariant(log.action_type)">
                {{ actionTypeLabels[log.action_type] }}
              </Badge>
            </TableCell>
            <TableCell>
              <div class="space-y-1">
                <Badge variant="outline">
                  {{ entityTypeLabels[log.entity_type] }}
                </Badge>
                <div class="text-xs text-muted-foreground">
                  {{ log.entity_id }}
                </div>
              </div>
            </TableCell>
            <TableCell>
              <div class="max-w-md">
                <div class="text-sm">{{ log.description }}</div>
                <div v-if="log.details" class="text-xs text-muted-foreground mt-1">
                  {{ JSON.stringify(log.details) }}
                </div>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- Пагинация -->
    <div class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Страница {{ page }} из {{ totalPages }} (всего записей: {{ logsData?.total || 0 }})
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="page === 1" @click="prevPage">
          Назад
        </Button>
        <Button
          variant="outline"
          size="sm"
          :disabled="page === totalPages || totalPages === 0"
          @click="nextPage"
        >
          Вперёд
        </Button>
      </div>
    </div>
  </div>
</template>
