<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { ScrollText, SlidersHorizontal, X } from 'lucide-vue-next'
import type { EventResponse, EventSeverity, EventSource } from '@/client'
import {
  listEventsApiEventsGetOptions,
  listEventTypesApiEventsTypesGetOptions,
} from '@/client/@tanstack/vue-query.gen'
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
  ACTOR_LABELS,
  SEVERITY_LABELS,
  SEVERITY_VARIANTS,
  SOURCE_LABELS,
  eventDomain,
} from '@/lib/events'
import { formatDateTime, formatRelative } from '@/lib/format'

const ALL = 'all'

const route = useRoute()
const { page, pageSize, searchInput, search } = useListQuery({ size: 25 })

const source = ref<EventSource | typeof ALL>(ALL)
const severity = ref<EventSeverity | typeof ALL>(ALL)
const domain = ref<string>(ALL)
const actorId = ref('')
const chatId = ref('')
const selected = ref<EventResponse | null>(null)

/** Реестр типов приходит с бэкенда: подписи и фильтры не дублируются здесь. */
const { data: types } = useQuery(listEventTypesApiEventsTypesGetOptions())

const titles = computed(() => new Map((types.value ?? []).map((item) => [item.type, item.title])))

/** Фильтр по домену (`role.*`), а не по каждому типу: типов десятки. */
const domains = computed(() => {
  const found = new Map<string, string>()
  for (const item of types.value ?? []) {
    const name = eventDomain(item.type)
    if (!found.has(name)) found.set(name, name)
  }
  return [...found.keys()].sort()
})

/** Ссылка «в журнале» из карточки участника приходит с готовым фильтром. */
watch(
  () => route.query.actor_id,
  (value) => {
    actorId.value = typeof value === 'string' ? value : ''
  },
  { immediate: true },
)

watch(
  () => route.query.chat_id,
  (value) => {
    chatId.value = typeof value === 'string' ? value : ''
  },
  { immediate: true },
)

const filters = computed(() => ({
  type: domain.value === ALL ? undefined : `${domain.value}.*`,
  source: source.value === ALL ? undefined : source.value,
  severity: severity.value === ALL ? undefined : severity.value,
  actor_id: actorId.value || undefined,
  chat_id: chatId.value || undefined,
  search_query: search.value || undefined,
}))

watch(filters, () => {
  page.value = 1
})

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listEventsApiEventsGetOptions({
      query: { page: page.value, size: pageSize.value, ...filters.value },
    }),
  ),
)

function eventTitle(type: string) {
  return titles.value.get(type) ?? type
}

/** Активные фильтры показываем чипами: иначе непонятно, почему список короткий. */
const chips = computed(() => {
  const items: { key: string; label: string; clear: () => void }[] = []
  if (domain.value !== ALL)
    items.push({
      key: 'type',
      label: `Раздел: ${domain.value}`,
      clear: () => (domain.value = ALL),
    })
  if (source.value !== ALL)
    items.push({
      key: 'source',
      label: `Источник: ${SOURCE_LABELS[source.value]}`,
      clear: () => (source.value = ALL),
    })
  if (severity.value !== ALL)
    items.push({
      key: 'severity',
      label: `Уровень: ${SEVERITY_LABELS[severity.value]}`,
      clear: () => (severity.value = ALL),
    })
  if (actorId.value)
    items.push({
      key: 'actor_id',
      label: `Кто: ${actorId.value}`,
      clear: () => (actorId.value = ''),
    })
  if (chatId.value)
    items.push({
      key: 'chat_id',
      label: `Чат: ${chatId.value}`,
      clear: () => (chatId.value = ''),
    })
  return items
})

function clearAll() {
  domain.value = ALL
  source.value = ALL
  severity.value = ALL
  actorId.value = ''
  chatId.value = ''
  searchInput.value = ''
}

function prettyPayload(payload: unknown) {
  return JSON.stringify(payload, null, 2)
}
</script>

<template>
  <div>
    <PageHeader />

    <DataToolbar v-model:search="searchInput" placeholder="Поиск по описанию">
      <template #filters>
        <Select v-model="domain">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любой раздел</SelectItem>
            <SelectItem v-for="name in domains" :key="name" :value="name">
              {{ name }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="source">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любой источник</SelectItem>
            <SelectItem v-for="(label, value) in SOURCE_LABELS" :key="value" :value="value">
              {{ label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="severity">
          <SelectTrigger size="sm" class="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem :value="ALL">Любой уровень</SelectItem>
            <SelectItem v-for="(label, value) in SEVERITY_LABELS" :key="value" :value="value">
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
              <Label for="chat-id">Чат (id)</Label>
              <Input id="chat-id" v-model="chatId" placeholder="123456@chat.agent" />
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
      :empty-title="chips.length || search ? 'Под фильтры ничего не подошло' : 'Событий пока нет'"
      :empty-description="
        chips.length || search
          ? 'Сбросьте часть фильтров или измените запрос.'
          : 'Здесь появится всё, что делают люди, бот и внешние системы.'
      "
      @retry="refetch()"
    >
      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead class="w-36">Когда</TableHead>
            <TableHead class="w-44">Событие</TableHead>
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
                <TooltipTrigger as="span">{{ formatRelative(entry.ts) }}</TooltipTrigger>
                <TooltipContent>{{ formatDateTime(entry.ts) }}</TooltipContent>
              </Tooltip>
            </TableCell>
            <TableCell>
              <Badge :variant="SEVERITY_VARIANTS[entry.severity]">
                {{ eventTitle(entry.type) }}
              </Badge>
            </TableCell>
            <TableCell>
              <div class="truncate">{{ entry.summary }}</div>
              <div class="flex items-center gap-1.5 text-xs text-muted-foreground">
                {{ SOURCE_LABELS[entry.source] }}
                <CopyableId v-if="entry.chat_id" :value="entry.chat_id" :max="24" />
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
      items-label="событий"
      @update:page="page = $event"
    />

    <Sheet :open="selected !== null" @update:open="selected = null">
      <SheetContent class="w-full gap-0 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{{ selected?.summary }}</SheetTitle>
          <SheetDescription>
            {{ selected ? formatDateTime(selected.ts) : '' }}
          </SheetDescription>
        </SheetHeader>
        <div v-if="selected" class="space-y-4 overflow-y-auto px-4 pb-6 text-sm">
          <dl class="divide-y">
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Событие</dt>
              <dd class="text-right">
                {{ eventTitle(selected.type) }}
                <span class="block font-mono text-xs text-muted-foreground">
                  {{ selected.type }}
                </span>
              </dd>
            </div>
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Источник</dt>
              <dd>{{ SOURCE_LABELS[selected.source] }}</dd>
            </div>
            <div class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Уровень</dt>
              <dd>{{ SEVERITY_LABELS[selected.severity] }}</dd>
            </div>
            <div v-if="selected.entity_id" class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Объект</dt>
              <dd class="text-right">
                {{ selected.entity_type }}
                <CopyableId :value="selected.entity_id" :max="30" class="block" />
              </dd>
            </div>
            <div v-if="selected.chat_id" class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Чат</dt>
              <dd>
                <RouterLink
                  :to="`/chats/${selected.chat_id}`"
                  class="font-mono text-xs hover:underline"
                >
                  {{ selected.chat_id }}
                </RouterLink>
              </dd>
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
            <div v-if="selected.trace_id" class="flex justify-between gap-4 py-2">
              <dt class="text-muted-foreground">Трассировка</dt>
              <dd>
                <!-- По этому идентификатору находятся строки логов в Grafana. -->
                <CopyableId :value="selected.trace_id" :max="24" />
              </dd>
            </div>
          </dl>
          <div v-if="selected.payload">
            <p class="mb-1.5 text-xs text-muted-foreground">Подробности</p>
            <pre class="overflow-x-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs">{{
              prettyPayload(selected.payload)
            }}</pre>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
