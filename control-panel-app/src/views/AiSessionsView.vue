<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Bot, CircleAlert, Coins, MessagesSquare } from 'lucide-vue-next'
import type { AgentSessionResponse, SessionStatus } from '@/client'
import {
  getSessionApiAiSessionsSessionIdGetOptions,
  getStatusApiAiStatusGetOptions,
  getUsageApiAiUsageGetOptions,
  listSessionsApiAiSessionsGetOptions,
} from '@/client/@tanstack/vue-query.gen'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import DataToolbar from '@/components/data/DataToolbar.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import StatTile from '@/components/data/StatTile.vue'
import AiUsageChart from '@/components/AiUsageChart.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
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
  MESSAGE_ROLE_LABELS,
  SESSION_STATUS_LABELS,
  SESSION_STATUS_VARIANTS,
  formatTokens,
} from '@/lib/ai'
import { formatDateTime, formatRelative } from '@/lib/format'
import { plural } from '@/lib/plural'

const ALL = 'all'
const DAYS = 14

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const { page, pageSize } = useListQuery({ size: 25 })
const status = ref<SessionStatus | typeof ALL>(ALL)
const selectedId = ref<string | null>(null)

// `useListQuery` сбрасывает страницу только на поиске. Без этого выбор
// состояния на пятой странице показывал бы пустой список при наличии
// результатов.
watch(status, () => {
  page.value = 1
})

/** Без статуса пустой список не отличить от выключенного агента. */
const { data: agent } = useQuery(getStatusApiAiStatusGetOptions())

const { data: usage } = useQuery(getUsageApiAiUsageGetOptions({ query: { days: DAYS } }))

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listSessionsApiAiSessionsGetOptions({
      query: {
        page: page.value,
        size: pageSize.value,
        session_status: status.value === ALL ? undefined : status.value,
      },
    }),
  ),
)

/** Карточка диалога грузится по требованию: истории бывают длинные. */
const { data: detail, isPending: detailPending } = useQuery(
  computed(() => ({
    ...getSessionApiAiSessionsSessionIdGetOptions({
      path: { session_id: selectedId.value ?? '' },
    }),
    enabled: selectedId.value !== null,
  })),
)

const totals = computed(() => usage.value?.totals)

/** Расход считаем в обе стороны: платят и за вход, и за выход. */
const totalTokens = computed(() =>
  totals.value ? totals.value.tokens_in + totals.value.tokens_out : 0,
)

const budget = computed(() => usage.value?.daily_token_budget ?? 0)
const spentToday = computed(() => usage.value?.spent_today ?? 0)
const budgetPercent = computed(() =>
  budget.value > 0 ? Math.min(100, Math.round((spentToday.value / budget.value) * 100)) : 0,
)

function open(session: AgentSessionResponse) {
  selectedId.value = session.id
}
</script>

<template>
  <div class="space-y-8">
    <PageHeader />

    <Alert v-if="agent && !agent.enabled" variant="default">
      <CircleAlert class="size-4" />
      <AlertTitle>Агент выключен</AlertTitle>
      <AlertDescription>
        {{
          agent.configured
            ? 'Настройки на месте, но агент выключен настройкой ai_enabled — команда /ai не отвечает.'
            : 'В .env не хватает AI_ENABLED, AI_API_KEY или AI_MODEL — команда /ai не отвечает.'
        }}
      </AlertDescription>
    </Alert>

    <div
      class="grid grid-cols-2 divide-y rounded-lg border sm:grid-cols-4 sm:divide-y-0 sm:divide-x"
    >
      <StatTile
        label="Диалогов"
        :value="totals?.sessions"
        :hint="`за ${DAYS} дней`"
        :icon="MessagesSquare"
        :loading="!usage"
      />
      <StatTile
        label="Токенов"
        :value="totals ? formatTokens(totalTokens) : null"
        :hint="totals ? `${formatTokens(totals.tokens_in)} на вход` : null"
        :icon="Coins"
        :loading="!usage"
      />
      <StatTile
        v-if="isAdmin"
        label="Спрашивали"
        :value="totals?.users"
        :hint="totals ? plural(totals.users, 'человек', 'человека', 'человек') : null"
        :icon="Bot"
        :loading="!usage"
      />
      <StatTile
        label="Сорвалось"
        :value="totals?.failed"
        hint="ошибка модели или шлюза"
        :icon="CircleAlert"
        :loading="!usage"
      />
    </div>

    <PageSection
      title="Расход по дням"
      :description="`Токены на вход и выход суммарно, за ${DAYS} дней`"
    >
      <AiUsageChart v-if="usage" :points="usage.by_day" />
    </PageSection>

    <PageSection
      v-if="budget > 0"
      title="Суточный лимит"
      description="Столько токенов агент тратит на одного человека в сутки; дальше он отказывает"
    >
      <div class="space-y-2">
        <Progress :model-value="budgetPercent" />
        <p class="text-sm text-muted-foreground">
          Сегодня израсходовано {{ formatTokens(spentToday) }} из {{ formatTokens(budget) }}
        </p>
      </div>
    </PageSection>

    <PageSection v-if="isAdmin && usage?.top_users.length" title="Кто спрашивает чаще">
      <div class="divide-y rounded-lg border">
        <div
          v-for="row in usage.top_users"
          :key="row.id"
          class="flex items-center justify-between gap-4 px-4 py-2.5 text-sm"
        >
          <RouterLink :to="`/chat-users/${row.id}`" class="truncate hover:underline">
            {{ row.name }}
          </RouterLink>
          <div class="flex shrink-0 items-center gap-4 text-muted-foreground">
            <span
              >{{ row.sessions }} {{ plural(row.sessions, 'диалог', 'диалога', 'диалогов') }}</span
            >
            <span class="tabular-nums">{{ formatTokens(row.tokens) }}</span>
          </div>
        </div>
      </div>
    </PageSection>

    <PageSection
      title="Диалоги"
      :description="isAdmin ? 'Все обращения к агенту' : 'Ваши обращения к агенту'"
    >
      <DataToolbar>
        <template #filters>
          <Select v-model="status">
            <SelectTrigger size="sm" class="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem :value="ALL">Любое состояние</SelectItem>
              <SelectItem
                v-for="(label, value) in SESSION_STATUS_LABELS"
                :key="value"
                :value="value"
              >
                {{ label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </template>
      </DataToolbar>

      <DataTableShell
        :loading="isPending"
        :error="isError ? true : undefined"
        :empty="!data?.items.length"
        :columns="isAdmin ? 5 : 4"
        :rows="6"
        :empty-icon="Bot"
        empty-title="Диалогов пока нет"
        empty-description="Здесь появятся вопросы, заданные боту командой /ai."
        @retry="refetch()"
      >
        <template #header>
          <TableHeader>
            <TableRow>
              <TableHead class="w-32">Когда</TableHead>
              <TableHead>Вопрос</TableHead>
              <TableHead v-if="isAdmin" class="w-44">Кто</TableHead>
              <TableHead class="w-40">Где</TableHead>
              <TableHead class="w-36">Состояние</TableHead>
            </TableRow>
          </TableHeader>
        </template>

        <template #body>
          <TableBody>
            <!-- Строка открывается и с клавиатуры: карточка диалога —
                 единственный способ увидеть ход разговора. -->
            <TableRow
              v-for="row in data?.items ?? []"
              :key="row.id"
              class="cursor-pointer"
              tabindex="0"
              @click="open(row)"
              @keydown.enter.self="open(row)"
              @keydown.space.self.prevent="open(row)"
            >
              <TableCell class="whitespace-nowrap text-muted-foreground">
                <Tooltip :delay-duration="400">
                  <TooltipTrigger as="span">{{ formatRelative(row.created_at) }}</TooltipTrigger>
                  <TooltipContent>{{ formatDateTime(row.created_at) }}</TooltipContent>
                </Tooltip>
              </TableCell>
              <TableCell>
                <div class="truncate">{{ row.question ?? '—' }}</div>
                <div class="text-xs text-muted-foreground tabular-nums">
                  {{ formatTokens(row.tokens_in + row.tokens_out) }} токенов
                </div>
              </TableCell>
              <TableCell v-if="isAdmin">
                <RouterLink :to="`/chat-users/${row.user_id}`" class="text-sm hover:underline">
                  {{ row.user_name }}
                </RouterLink>
              </TableCell>
              <TableCell>
                <RouterLink
                  v-if="row.chat_title"
                  :to="`/chats/${row.chat_id}`"
                  class="truncate text-sm hover:underline"
                >
                  {{ row.chat_title }}
                </RouterLink>
                <!-- У обсуждения свой chatId, которого в чатах нет: ссылке
                     вести некуда, показываем идентификатор. -->
                <CopyableId v-else :value="row.chat_id" :max="20" />
              </TableCell>
              <TableCell>
                <Badge :variant="SESSION_STATUS_VARIANTS[row.status]">
                  {{ SESSION_STATUS_LABELS[row.status] }}
                </Badge>
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
        items-label="диалогов"
        @update:page="page = $event"
      />
    </PageSection>

    <Sheet :open="selectedId !== null" @update:open="selectedId = null">
      <SheetContent class="w-full gap-0 sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{{ detail?.session.question ?? 'Диалог с агентом' }}</SheetTitle>
          <SheetDescription>
            {{ detail ? formatDateTime(detail.session.created_at) : '' }}
          </SheetDescription>
        </SheetHeader>
        <div class="space-y-4 overflow-y-auto px-4 pb-6 text-sm">
          <p v-if="detailPending" class="text-muted-foreground">Загружаю…</p>
          <template v-else-if="detail">
            <dl class="divide-y">
              <div class="flex justify-between gap-4 py-2">
                <dt class="text-muted-foreground">Состояние</dt>
                <dd>
                  <Badge :variant="SESSION_STATUS_VARIANTS[detail.session.status]">
                    {{ SESSION_STATUS_LABELS[detail.session.status] }}
                  </Badge>
                </dd>
              </div>
              <div class="flex justify-between gap-4 py-2">
                <dt class="text-muted-foreground">Кто спросил</dt>
                <dd>{{ detail.session.user_name }}</dd>
              </div>
              <div class="flex justify-between gap-4 py-2">
                <dt class="text-muted-foreground">Где</dt>
                <dd class="text-right">
                  {{ detail.session.chat_title ?? '—' }}
                  <CopyableId :value="detail.session.chat_id" :max="26" class="block" />
                </dd>
              </div>
              <div class="flex justify-between gap-4 py-2">
                <dt class="text-muted-foreground">Токены</dt>
                <dd class="tabular-nums">
                  {{ detail.session.tokens_in }} на вход, {{ detail.session.tokens_out }} на выход
                </dd>
              </div>
            </dl>

            <div class="space-y-3">
              <p class="text-xs text-muted-foreground">
                Ход диалога. Подложенная в запрос переписка чата здесь не показывается — читать чаты
                через панель нельзя.
              </p>
              <div
                v-for="message in detail.messages"
                :key="message.id"
                class="rounded-lg border p-3"
                :class="message.role === 'user' ? 'bg-muted/40' : ''"
              >
                <p class="mb-1 text-xs text-muted-foreground">
                  {{ MESSAGE_ROLE_LABELS[message.role] ?? message.role }}
                </p>
                <p class="whitespace-pre-wrap">{{ message.content || '—' }}</p>
              </div>
            </div>
          </template>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
