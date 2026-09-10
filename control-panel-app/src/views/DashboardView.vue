<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { MessagesSquare, ShieldCheck, Users, Webhook } from 'lucide-vue-next'
import {
  getOverviewApiOverviewGetOptions,
  listLogsApiLogsGetOptions,
} from '@/client/@tanstack/vue-query.gen'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import StatTile from '@/components/data/StatTile.vue'
import ActivityChart from '@/components/ActivityChart.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ACTION_LABELS, ACTION_VARIANTS, ACTOR_LABELS } from '@/lib/audit'
import { formatRelative } from '@/lib/format'
import { plural } from '@/lib/plural'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const { data: overview, isPending: overviewPending } = useQuery(
  getOverviewApiOverviewGetOptions({ query: { days: 14 } }),
)

const { data: logs, isPending: logsPending } = useQuery(
  computed(() => ({
    ...listLogsApiLogsGetOptions({ query: { page: 1, size: 8 } }),
    enabled: isAdmin.value,
  })),
)

const counts = computed(() => overview.value?.counts)
const activity = computed(() => overview.value?.activity ?? [])
const totalActions = computed(() =>
  activity.value.reduce((sum, point) => sum + point.count, 0),
)

const webhooksHint = computed(() => {
  const all = counts.value?.webhooks ?? 0
  const active = counts.value?.webhooks_active ?? 0
  if (all === 0) return null
  return active === all ? 'все активны' : `${all - active} выключено`
})
</script>

<template>
  <div class="space-y-8">
    <PageHeader />

    <div class="grid grid-cols-2 divide-y rounded-lg border sm:grid-cols-4 sm:divide-y-0 sm:divide-x">
      <StatTile
        label="Чаты"
        :value="counts?.chats"
        :icon="MessagesSquare"
        :loading="overviewPending"
      />
      <StatTile
        label="Участники"
        :value="counts?.chat_users"
        :icon="Users"
        :loading="overviewPending"
      />
      <StatTile
        label="Роли"
        :value="counts?.roles"
        :icon="ShieldCheck"
        :loading="overviewPending"
      />
      <StatTile
        label="Вебхуки"
        :value="counts?.webhooks"
        :hint="webhooksHint"
        :icon="Webhook"
        :loading="overviewPending"
      />
    </div>

    <PageSection
      v-if="isAdmin"
      title="Активность"
      :description="`${totalActions} ${plural(totalActions, 'действие', 'действия', 'действий')} за две недели`"
    >
      <Skeleton v-if="overviewPending" class="h-[180px] w-full" />
      <ActivityChart v-else :points="activity" />
    </PageSection>

    <PageSection v-if="isAdmin" title="Последние действия">
      <template #actions>
        <Button variant="ghost" size="sm" as-child>
          <RouterLink to="/logs">Весь журнал</RouterLink>
        </Button>
      </template>

      <div v-if="logsPending" class="space-y-3">
        <Skeleton v-for="row in 5" :key="row" class="h-5 w-full" />
      </div>
      <p v-else-if="!logs?.items.length" class="py-6 text-sm text-muted-foreground">
        Действий пока не было.
      </p>
      <ul v-else class="divide-y">
        <li
          v-for="entry in logs.items"
          :key="entry.id"
          class="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5 text-sm"
        >
          <span class="w-28 shrink-0 tabular-nums text-muted-foreground">
            {{ formatRelative(entry.timestamp) }}
          </span>
          <Badge :variant="ACTION_VARIANTS[entry.action_type]">
            {{ ACTION_LABELS[entry.action_type] }}
          </Badge>
          <span class="min-w-0 flex-1">{{ entry.description ?? entry.entity_id }}</span>
          <span class="shrink-0 text-xs text-muted-foreground">
            {{ ACTOR_LABELS[entry.actor_type] }}
          </span>
        </li>
      </ul>
    </PageSection>

    <PageSection v-else title="Что дальше">
      <p class="text-sm text-muted-foreground">
        Роли и состав чатов — в разделе «Чаты и люди». Вебхуки для внешних систем —
        в «Интеграциях».
      </p>
    </PageSection>
  </div>
</template>
