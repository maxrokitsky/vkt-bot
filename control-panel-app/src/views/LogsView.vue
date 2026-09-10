<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { ScrollText, SlidersHorizontal, X } from 'lucide-vue-next'
import type { ActionType, ActorType, EntityType, LogEntryResponse } from '@/client'
import { listLogsApiLogsGetOptions } from '@/client/@tanstack/vue-query.gen'
import PageHeader from '@/components/layout/PageHeader.vue'
import DataToolbar from '@/components/data/DataToolbar.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useListQuery } from '@/composables/useListQuery'
import {
  ACTION_LABELS,
  ACTION_VARIANTS,
  ACTOR_LABELS,
  ENTITY_LABELS,
} from '@/lib/audit'
import { formatDateTime, formatRelative } from '@/lib/format'

const ALL = 'all'

const route = useRoute()
const { page, pageSize, searchInput, search } = useListQuery({ size: 25 })

const actorType = ref<ActorType | typeof ALL>(ALL)
const actionType = ref<ActionType | typeof ALL>(ALL)
const entityType = ref<EntityType | typeof ALL>(ALL)
const actorId = ref('')
const entityId = ref('')
const selected = ref<LogEntryResponse | null>(null)

/** Ссылка «в журнале» из карточки участника приходит с готовым фильтром. */
watch(
  () => route.query.actor_id,
  (value) => {
    actorId.value = typeof value === 'string' ? value : ''
  },
  { immediate: true },
)

const filters = computed(() => ({
  actor_type: actorType.value === ALL ? undefined : actorType.value,
  action_type: actionType.value === ALL ? undefined : actionType.value,
  entity_type: entityType.value === ALL ? undefined : entityType.value,
  actor_id: actorId.value || undefined,
  entity_id: entityId.value || undefined,
  search_query: search.value || undefined,
}))

watch(filters, () => {
  page.value = 1
})

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listLogsApiLogsGetOptions({
      query: { page: page.value, size: pageSize.value, ...filters.value },
    }),
  ),
)

/** Активные фильтры показываем чипами: иначе непонятно, почему список короткий. */
const chips = computed(() => {
  const items: { key: string; label: string; clear: () => void }[] = []
  if (actorType.value !== ALL)
    items.push({
      key: 'actor_type',
      label: `Источник: ${ACTOR_LABELS[actorType.value]}`,
      clear: () => (actorType.value = ALL),
    })
  if (actionType.value !== ALL)
    items.push({
      key: 'action_type',
      label: `Действие: ${ACTION_LABELS[actionType.value]}`,
      clear: () => (actionType.value = ALL),
    })
  if (entityType.value !== ALL)
    items.push({
      key: 'entity_type',
      label: `Объект: ${ENTITY_LABELS[entityType.value]}`,
      clear: () => (entityType.value = ALL),
    })
  if (actorId.value)
    items.push({
      key: 'actor_id',
      label: `Кто: ${actorId.value}`,
      clear: () => (actorId.value = ''),
    })
  if (entityId.value)
    items.push({
      key: 'entity_id',
      label: `Объект: ${entityId.value}`,
      clear: () => (entityId.value = ''),
    })
  return items
})

function clearAll() {
  actorType.value = ALL
  actionType.value = ALL
  entityType.value = ALL
  actorId.value = ''
  entityId.value = ''
  searchInput.value = ''
}

function prettyDetails(details: unknown) {
  return JSON.stringify(details, null, 2)
}
</script>

<template>
  <div>
    <PageHeader />

    <DataToolbar
      v-model:search="searchInput"
      placeholder="Поиск по описанию"
    >
      <template #filters>
        <Select v-model="actorType">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любой источник</SelectItem>
            <SelectItem v-for="(label, value) in ACTOR_LABELS" :key="value" :value="value">
              {{ label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="actionType">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любое действие</SelectItem>
            <SelectItem v-for="(label, value) in ACTION_LABELS" :key="value" :value="value">
              {{ label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="entityType">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любой объект</SelectItem>
            <SelectItem v-for="(label, value) in ENTITY_LABELS" :key="value" :value="value">
              {{ label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Popover>
          <PopoverTrigger as-child>
            <Button variant="outline" size="sm">
              <SlidersHorizontal class="size-4" />
              Ещё
            </Button>
          </PopoverTrigger>
          <PopoverContent class="w-72 space-y-3" align="start">
            <div class="space-y-1.5">
              <Label for="actor-id">Кто (id)</Label>
              <Input id="actor-id" v-model="actorId" placeholder="user@example.com" />
            </div>
            <div class="space-y-1.5">
              <Label for="entity-id">Объект (id)</Label>
              <Input id="entity-id" v-model="entityId" placeholder="id роли, чата, участника" />
            </div>
          </PopoverContent>
        </Popover>
      </template>
    </DataToolbar>

    <div v-if="chips.length" class="mb-4 flex flex-wrap items-center gap-2">
      <Badge
        v-for="chip in chips"
        :key="chip.key"
        variant="secondary"
        class="cursor-pointer gap-1 pr-1"
        @click="chip.clear()"
      >
        {{ chip.label }}
        <X class="size-3" />
      </Badge>
      <Button variant="ghost" size="sm" class="h-6 text-muted-foreground" @click="clearAll">
        Сбросить всё
      </Button>
    </div>

    <DataTableShell
      :loading="isPending"
      :error="isError ? true : undefined"
      :empty="!data?.items.length"
      :columns="4"
      :rows="8"
      :empty-icon="ScrollText"
      :empty-title="chips.length || search ? 'Под фильтры ничего не подошло' : 'Записей пока нет'"
      :empty-description="
        chips.length || search
          ? 'Сбросьте часть фильтров или измените запрос.'
          : 'Здесь появятся изменения, сделанные через панель и бота.'
      "
      @retry="refetch()"
    >
      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead class="w-36">Когда</TableHead>
            <TableHead class="w-32">Действие</TableHead>
            <TableHead>Что произошло</TableHead>
            <TableHead class="w-44">Кто</TableHead>
          </TableRow>
        </TableHeader>
      </template>

      <template #body>
        <TableBody>
          <TableRow
            v-for="entry in data?.items ?? []"
            :key="entry.id"
            class="cursor-pointer"
            @click="selected = entry"
          >
            <TableCell class="whitespace-nowrap text-muted-foreground">
              <Tooltip :delay-duration="400">
                <TooltipTrigger as="span">{{ formatRelative(entry.timestamp) }}</TooltipTrigger>
                <TooltipContent>{{ formatDateTime(entry.timestamp) }}</TooltipContent>
              </Tooltip>
            </TableCell>
            <TableCell>
              <Badge :variant="ACTION_VARIANTS[entry.action_type]">
                {{ ACTION_LABELS[entry.action_type] }}
              </Badge>
            </TableCell>
            <TableCell>
              <div class="truncate">{{ entry.description ?? '—' }}</div>
              <div class="flex items-center gap-1.5 text-xs text-muted-foreground">
                {{ ENTITY_LABELS[entry.entity_type] }}
                <CopyableId :value="entry.entity_id" :max="24" />
              </div>
            </TableCell>
            <TableCell>
              <div class="text-sm">{{ ACTOR_LABELS[entry.actor_type] }}</div>
              <CopyableId v-if="entry.actor_id" :value="entry.actor_id" :max="22" />
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
      items-label="записей"
      @update:page="page = $event"
    />

    <Sheet :open="selected !== null" @update:open="selected = null">
      <SheetContent class="w-full gap-0 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{{ selected?.description ?? 'Запись журнала' }}</SheetTitle>
          <SheetDescription>
            {{ selected ? formatDateTime(selected.timestamp) : '' }}
          </SheetDescription>
        </SheetHeader>
        <div v-if="selected" class="space-y-4 overflow-y-auto px-4 pb-6 text-sm">
          <dl class="divide-y">
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Действие</dt>
              <dd>{{ ACTION_LABELS[selected.action_type] }}</dd>
            </div>
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Объект</dt>
              <dd class="text-right">
                {{ ENTITY_LABELS[selected.entity_type] }}
                <CopyableId :value="selected.entity_id" :max="30" class="block" />
              </dd>
            </div>
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Источник</dt>
              <dd>{{ ACTOR_LABELS[selected.actor_type] }}</dd>
            </div>
            <div v-if="selected.actor_id" class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Кто</dt>
              <dd>
                <RouterLink
                  :to="`/chat-users/${selected.actor_id}`"
                  class="font-mono text-xs hover:underline"
                >
                  {{ selected.actor_id }}
                </RouterLink>
              </dd>
            </div>
          </dl>
          <div v-if="selected.details">
            <p class="mb-1.5 text-xs text-muted-foreground">Подробности</p>
            <pre
              class="overflow-x-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs"
            >{{ prettyDetails(selected.details) }}</pre>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
