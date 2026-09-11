<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { useClipboard } from '@vueuse/core'
import { Bot, Check, Crown, Link2, ScrollText, Send, Shield, Users, Webhook } from 'lucide-vue-next'
import {
  getChatApiChatsChatIdGetOptions,
  listChatEventsApiChatsChatIdEventsGetOptions,
  listChatUsersApiChatUsersGetOptions,
  listChatWebhooksApiChatsChatIdWebhooksGetOptions,
  listEventTypesApiEventsTypesGetOptions,
} from '@/client/@tanstack/vue-query.gen'
import type { ChatResponse } from '@/client'
import { API_BASE_URL } from '@/hey-api'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import UserAvatar from '@/components/data/UserAvatar.vue'
import FieldRow from '@/components/layout/FieldRow.vue'
import EmptyState from '@/components/data/EmptyState.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import SendMessageDialog from '@/components/SendMessageDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useListQuery } from '@/composables/useListQuery'
import { chatTypeLabel } from '@/lib/chats'
import { SEVERITY_VARIANTS, SOURCE_LABELS } from '@/lib/events'
import { formatDateTime, formatRelative } from '@/lib/format'
import { plural } from '@/lib/plural'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const chatId = computed(() => route.params.id as string)
const isAdmin = computed(() => authStore.isAdmin)

const { copy, copied } = useClipboard({ legacy: true })
const chatToMessage = ref<ChatResponse | null>(null)
const { page, pageSize, searchInput, search } = useListQuery()

const { data: chat, isPending } = useQuery(
  computed(() => getChatApiChatsChatIdGetOptions({ path: { chat_id: chatId.value } })),
)

const { data: members, isPending: membersPending } = useQuery(
  computed(() =>
    listChatUsersApiChatUsersGetOptions({
      query: {
        chat_id: chatId.value,
        page: page.value,
        size: pageSize.value,
        search: search.value || undefined,
      },
    }),
  ),
)

/** Обычному пользователю API отдаёт только его собственные вебхуки чата. */
const { data: webhooks } = useQuery(
  computed(() =>
    listChatWebhooksApiChatsChatIdWebhooksGetOptions({ path: { chat_id: chatId.value } }),
  ),
)

/** Лента чата: только типы событий, которым место на этой странице. */
const { data: events } = useQuery(
  computed(() =>
    listChatEventsApiChatsChatIdEventsGetOptions({
      path: { chat_id: chatId.value },
      query: { page: 1, size: 20 },
    }),
  ),
)

const { data: eventTypes } = useQuery(listEventTypesApiEventsTypesGetOptions())
const eventTitles = computed(
  () => new Map((eventTypes.value ?? []).map((item) => [item.type, item.title])),
)

const membersDescription = computed(() => {
  const total = chat.value?.member_count ?? 0
  if (!total) return 'Состав приходит из событий чата'
  return `${total} ${plural(total, 'участник', 'участника', 'участников')}`
})

function webhookUrl(id: string) {
  return `${API_BASE_URL}/webhooks/${id}`
}
</script>

<template>
  <div class="space-y-8">
    <PageHeader :title="chat?.title || chatId" :description="chat?.about ?? null">
      <template #badges>
        <Badge v-if="chat" variant="outline">{{ chatTypeLabel(chat.type) }}</Badge>
        <Badge v-if="chat?.public" variant="secondary">Публичный</Badge>
        <Badge v-if="chat?.join_moderation" variant="secondary"> Вступление с одобрения </Badge>
      </template>
      <template #actions>
        <Button v-if="isAdmin && chat" variant="outline" size="sm" @click="chatToMessage = chat">
          <Send class="size-4" />
          Отправить сообщение
        </Button>
      </template>
      <template #below>
        <CopyableId v-if="chat?.title" :value="chatId" :max="40" class="mt-2" />
      </template>
    </PageHeader>

    <div v-if="isPending" class="space-y-4">
      <Skeleton class="h-6 w-40" />
      <Skeleton class="h-24 w-full" />
    </div>

    <template v-else-if="chat">
      <PageSection
        v-if="chat.rules || chat.invite_link"
        title="О чате"
        description="Данные из VK Teams — бот перечитывает их не чаще раза в неделю"
      >
        <div class="divide-y rounded-lg border px-4">
          <FieldRow v-if="chat.rules" label="Правила" stacked>
            <p class="text-sm whitespace-pre-line">{{ chat.rules }}</p>
          </FieldRow>
          <FieldRow
            v-if="chat.invite_link"
            label="Ссылка-приглашение"
            description="По ней в чат заходят без спроса"
          >
            <a
              :href="chat.invite_link"
              target="_blank"
              rel="noreferrer"
              class="text-sm break-all hover:underline"
            >
              {{ chat.invite_link }}
            </a>
          </FieldRow>
        </div>
      </PageSection>

      <PageSection title="Участники" :description="membersDescription">
        <template #actions>
          <Input
            v-model="searchInput"
            placeholder="Имя или id"
            class="h-8 w-full sm:w-56"
            aria-label="Поиск участника"
          />
        </template>

        <div v-if="membersPending" class="space-y-2">
          <Skeleton v-for="index in 3" :key="index" class="h-12 w-full" />
        </div>

        <template v-else-if="members?.items.length">
          <ul class="divide-y rounded-lg border">
            <li
              v-for="member in members.items"
              :key="member.id"
              class="flex cursor-pointer items-center justify-between gap-3 px-4 py-2.5 hover:bg-muted/50"
              @click="router.push(`/chat-users/${member.id}`)"
            >
              <div class="flex min-w-0 items-center gap-3">
                <UserAvatar :name="member.display_name" :src="member.photo_url" />
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium">{{ member.display_name }}</div>
                  <CopyableId
                    v-if="member.display_name !== member.id"
                    :value="member.id"
                    :max="32"
                  />
                </div>
              </div>
              <div class="flex shrink-0 flex-wrap items-center justify-end gap-1">
                <Badge v-for="role in member.roles" :key="role.id" variant="secondary">
                  {{ role.name }}
                </Badge>
                <Badge v-if="member.is_owner">
                  <Crown />
                  Владелец
                </Badge>
                <Badge v-else-if="member.is_superuser" variant="secondary">
                  <Shield />
                  Админ
                </Badge>
                <Badge v-if="member.is_bot" variant="outline">
                  <Bot />
                  Бот
                </Badge>
              </div>
            </li>
          </ul>

          <TablePagination
            :page="members.page"
            :size="members.size"
            :total="members.total"
            :pages="members.pages"
            items-label="участников"
            @update:page="page = $event"
          />
        </template>

        <EmptyState
          v-else
          :icon="Users"
          :title="search ? 'Никого не нашлось' : 'Участников пока нет'"
          :description="
            search
              ? 'Измените запрос — поиск идёт по имени, нику и id.'
              : 'Участники появляются, когда бот видит их в событиях чата.'
          "
        />
      </PageSection>

      <PageSection title="Что происходило" description="События этого чата">
        <template #actions>
          <Button variant="ghost" size="sm" as-child>
            <RouterLink :to="{ path: '/events', query: { chat_id: chatId } }">
              Все события чата
            </RouterLink>
          </Button>
        </template>

        <ul v-if="events?.items.length" class="divide-y rounded-lg border">
          <li
            v-for="entry in events.items"
            :key="entry.id"
            class="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-sm"
          >
            <span
              class="w-28 shrink-0 tabular-nums text-muted-foreground"
              :title="formatDateTime(entry.ts)"
            >
              {{ formatRelative(entry.ts) }}
            </span>
            <Badge :variant="SEVERITY_VARIANTS[entry.severity]">
              {{ eventTitles.get(entry.type) ?? entry.type }}
            </Badge>
            <span class="min-w-0 flex-1">{{ entry.summary }}</span>
            <span class="shrink-0 text-xs text-muted-foreground">
              {{ SOURCE_LABELS[entry.source] }}
            </span>
          </li>
        </ul>

        <EmptyState
          v-else
          :icon="ScrollText"
          title="Событий пока нет"
          description="Здесь появятся вход и уход участников, призывы по ролям, вызовы вебхуков и неудачные отправки."
        />
      </PageSection>

      <PageSection title="Вебхуки" description="Внешние системы, которые пишут в этот чат">
        <template #actions>
          <Button variant="ghost" size="sm" as-child>
            <RouterLink to="/webhooks">Все вебхуки</RouterLink>
          </Button>
        </template>

        <ul v-if="webhooks?.webhooks.length" class="divide-y rounded-lg border">
          <li
            v-for="webhook in webhooks.webhooks"
            :key="webhook.id"
            class="flex items-center justify-between gap-3 px-4 py-2.5"
          >
            <div class="min-w-0">
              <div class="truncate text-sm font-medium">{{ webhook.name }}</div>
              <button
                type="button"
                class="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                @click="copy(webhookUrl(webhook.id))"
              >
                <Check v-if="copied" class="size-3" />
                <Link2 v-else class="size-3" />
                /webhooks/{{ webhook.id }}
              </button>
            </div>
            <div class="shrink-0 text-right">
              <Badge v-if="webhook.is_active" variant="secondary">Активен</Badge>
              <Badge v-else variant="outline">Выключен</Badge>
              <div class="mt-1 text-xs text-muted-foreground">
                создан {{ formatRelative(webhook.created_at) }}
              </div>
            </div>
          </li>
        </ul>

        <EmptyState
          v-else
          :icon="Webhook"
          title="Вебхуков нет"
          description="Вебхук даёт внешней системе адрес и ключ, по которым она отправляет сообщение в этот чат."
        >
          <Button as-child>
            <RouterLink to="/webhooks">Создать вебхук</RouterLink>
          </Button>
        </EmptyState>
      </PageSection>
    </template>

    <SendMessageDialog :chat="chatToMessage" @update:chat="chatToMessage = $event" />
  </div>
</template>
