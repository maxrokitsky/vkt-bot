<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { Bot, Crown, Shield, Users } from 'lucide-vue-next'
import { listChatUsersApiChatUsersGetOptions } from '@/client/@tanstack/vue-query.gen'
import PageHeader from '@/components/layout/PageHeader.vue'
import DataToolbar from '@/components/data/DataToolbar.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Toggle } from '@/components/ui/toggle'
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useListQuery } from '@/composables/useListQuery'

const router = useRouter()
const { page, pageSize, searchInput, search } = useListQuery()

/** Фильтры-переключатели: их всего два, выпадающий список тут был бы лишним. */
const onlyAdmins = ref(false)
const onlyBots = ref(false)

const { data, isPending, isError, refetch } = useQuery(
  computed(() =>
    listChatUsersApiChatUsersGetOptions({
      query: { page: page.value, size: pageSize.value, search: search.value || undefined },
    }),
  ),
)

/** Фильтры считаются по загруженной странице — на бэкенде их пока нет. */
const rows = computed(() => {
  const items = data.value?.items ?? []
  return items
    .filter((user) => !onlyAdmins.value || user.is_superuser || user.is_owner)
    .filter((user) => !onlyBots.value || user.is_bot)
})

const filtered = computed(() => onlyAdmins.value || onlyBots.value)

function initials(name: string) {
  return name
    .split(/[\s.@_-]+/)
    .filter(Boolean)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}
</script>

<template>
  <div>
    <PageHeader />

    <DataToolbar
      v-model:search="searchInput"
      placeholder="Имя, ник или id"
    >
      <template #filters>
        <Toggle v-model:pressed="onlyAdmins" variant="outline" size="sm" class="gap-1.5">
          <Shield class="size-3.5" />
          Админы
        </Toggle>
        <Toggle v-model:pressed="onlyBots" variant="outline" size="sm" class="gap-1.5">
          <Bot class="size-3.5" />
          Боты
        </Toggle>
      </template>
    </DataToolbar>

    <DataTableShell
      :loading="isPending"
      :error="isError ? true : undefined"
      :empty="rows.length === 0"
      :columns="3"
      :empty-icon="Users"
      :empty-title="search || filtered ? 'Никого не нашлось' : 'Участников пока нет'"
      :empty-description="
        search || filtered
          ? 'Измените запрос или снимите фильтры.'
          : 'Участники появляются, когда бот попадает в чат и видит его состав.'
      "
      @retry="refetch()"
    >
      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead>Участник</TableHead>
            <TableHead>Роли</TableHead>
            <TableHead class="w-40">Статус</TableHead>
          </TableRow>
        </TableHeader>
      </template>

      <template #body>
        <TableBody>
          <TableRow
            v-for="user in rows"
            :key="user.id"
            class="cursor-pointer"
            @click="router.push(`/chat-users/${user.id}`)"
          >
            <TableCell>
              <div class="flex items-center gap-3">
                <Avatar class="size-8 rounded-md">
                  <AvatarFallback class="rounded-md text-xs">
                    {{ initials(user.display_name) }}
                  </AvatarFallback>
                </Avatar>
                <div class="min-w-0">
                  <div class="truncate font-medium">{{ user.display_name }}</div>
                  <CopyableId v-if="user.display_name !== user.id" :value="user.id" />
                </div>
              </div>
            </TableCell>
            <TableCell>
              <div v-if="user.roles.length" class="flex flex-wrap gap-1">
                <Badge v-for="role in user.roles" :key="role.id" variant="secondary">
                  {{ role.name }}
                </Badge>
              </div>
              <span v-else class="text-muted-foreground">—</span>
            </TableCell>
            <TableCell>
              <div class="flex flex-wrap gap-1">
                <Badge v-if="user.is_owner">
                  <Crown />
                  Владелец
                </Badge>
                <Badge v-else-if="user.is_superuser" variant="secondary">
                  <Shield />
                  Админ
                </Badge>
                <Badge v-if="user.is_bot" variant="outline">
                  <Bot />
                  Бот
                </Badge>
                <span v-if="!user.is_owner && !user.is_superuser && !user.is_bot" class="text-muted-foreground">
                  —
                </span>
              </div>
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
      items-label="участников"
      @update:page="page = $event"
    />
  </div>
</template>
