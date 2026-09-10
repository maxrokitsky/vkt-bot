<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { toast } from 'vue-sonner'
import {
  getBotSettingApiBotSettingsKeyGetOptions,
  getBotSettingApiBotSettingsKeyGetQueryKey,
  listBotSettingsApiBotSettingsGetOptions,
  listBotSettingsApiBotSettingsGetQueryKey,
  updateBotSettingApiBotSettingsKeyPutMutation,
} from '@/client/@tanstack/vue-query.gen'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import FieldRow from '@/components/layout/FieldRow.vue'
import StickySaveBar from '@/components/layout/StickySaveBar.vue'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime } from '@/lib/format'

const START_MESSAGE = 'start_message'
const THREADS_AUTOSUBSCRIBE = 'threads_autosubscribe'
const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on'])
const FALSE_VALUES = new Set(['0', 'false', 'no', 'off'])

const queryClient = useQueryClient()

const { data: startMessage, isPending: startPending } = useQuery(
  getBotSettingApiBotSettingsKeyGetOptions({ path: { key: START_MESSAGE } }),
)

const { data: allSettings, isPending: allPending } = useQuery(
  listBotSettingsApiBotSettingsGetOptions(),
)

/** Черновик приветствия. `null` — правок не было, показываем серверное. */
const draft = ref<string | null>(null)

watch(startMessage, () => {
  draft.value = null
})

const text = computed(() => draft.value ?? startMessage.value?.value ?? '')
const dirty = computed(() => draft.value !== null && draft.value !== startMessage.value?.value)

/** Значения хранятся строками; неизвестное написание — как включённое. */
const autosubscribe = computed(() => {
  const row = allSettings.value?.find((setting) => setting.key === THREADS_AUTOSUBSCRIBE)
  if (!row) return true
  const value = row.value.trim().toLowerCase()
  if (FALSE_VALUES.has(value)) return false
  if (TRUE_VALUES.has(value)) return true
  return true
})

const otherSettings = computed(() =>
  (allSettings.value ?? []).filter(
    (setting) => setting.key !== START_MESSAGE && setting.key !== THREADS_AUTOSUBSCRIBE,
  ),
)

const update = useMutation({
  ...updateBotSettingApiBotSettingsKeyPutMutation(),
  onSuccess: (_data, variables) => {
    queryClient.invalidateQueries({ queryKey: listBotSettingsApiBotSettingsGetQueryKey() })
    queryClient.invalidateQueries({
      queryKey: getBotSettingApiBotSettingsKeyGetQueryKey({ path: { key: variables.path.key } }),
    })
    draft.value = null
    toast.success('Сохранено')
  },
  onError: () => toast.error('Не удалось сохранить'),
})

function saveStartMessage() {
  update.mutate({ path: { key: START_MESSAGE }, body: { value: text.value } })
}

function toggleAutosubscribe(value: boolean) {
  update.mutate({
    path: { key: THREADS_AUTOSUBSCRIBE },
    body: {
      value: value ? 'true' : 'false',
      description: 'Подписывать бота на обсуждения в новых чатах',
    },
  })
}
</script>

<template>
  <div class="space-y-8">
    <PageHeader />

    <PageSection title="Приветствие" description="Ответ бота на команду /start">
      <Skeleton v-if="startPending" class="h-64 w-full" />
      <template v-else>
        <Textarea
          id="start-message"
          :model-value="text"
          rows="14"
          class="font-mono text-sm"
          placeholder="Что бот отвечает на /start"
          @update:model-value="draft = String($event)"
        />
        <p class="text-sm text-muted-foreground">
          Поддерживается MarkdownV2. Спецсимволы нужно экранировать, иначе VK Teams
          отклонит сообщение. Пустое значение вернёт текст по умолчанию.
        </p>
      </template>
    </PageSection>

    <PageSection title="Обсуждения" description="Треды внутри чатов">
      <Skeleton v-if="allPending" class="h-16 w-full" />
      <FieldRow
        v-else
        label="Подписываться на обсуждения"
        description="При добавлении в чат бот подпишется на все его обсуждения — иначе сообщения из тредов до него не доходят. Для отдельного чата это переключается командой /subscribethreads."
        for="autosubscribe"
      >
        <Switch
          id="autosubscribe"
          :model-value="autosubscribe"
          :disabled="update.isPending.value"
          @update:model-value="toggleAutosubscribe"
        />
      </FieldRow>
    </PageSection>

    <Collapsible v-if="otherSettings.length">
      <CollapsibleTrigger as-child>
        <Button variant="ghost" size="sm" class="text-muted-foreground">
          Остальные настройки ({{ otherSettings.length }})
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent class="pt-2">
        <dl class="divide-y rounded-lg border text-sm">
          <div v-for="setting in otherSettings" :key="setting.key" class="px-4 py-3">
            <dt class="font-mono text-xs text-muted-foreground">{{ setting.key }}</dt>
            <dd class="mt-1 break-words">{{ setting.value }}</dd>
            <dd class="mt-1 text-xs text-muted-foreground">
              изменено {{ formatDateTime(setting.updated_at) }}
            </dd>
          </div>
        </dl>
      </CollapsibleContent>
    </Collapsible>

    <StickySaveBar
      :dirty="dirty"
      :pending="update.isPending.value"
      @save="saveStartMessage"
      @reset="draft = null"
    />
  </div>
</template>
