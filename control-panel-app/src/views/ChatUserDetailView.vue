<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { Bot, Crown, MessagesSquare, Plus, Shield, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import {
  assignRoleToUserApiChatUsersUserIdRolesRoleIdPostMutation,
  getChatUserApiChatUsersUserIdGetOptions,
  getChatUserApiChatUsersUserIdGetQueryKey,
  listLogsApiLogsGetOptions,
  listRolesApiRolesGetOptions,
  removeRoleFromUserApiChatUsersUserIdRolesRoleIdDeleteMutation,
  updateChatUserApiChatUsersUserIdPatchMutation,
} from '@/client/@tanstack/vue-query.gen'
import { useAuthStore } from '@/stores/auth'
import { useConfirm } from '@/composables/useConfirm'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
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
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ACTION_LABELS, ACTION_VARIANTS } from '@/lib/audit'
import { chatTypeLabel } from '@/lib/chats'
import { formatRelative } from '@/lib/format'
import { plural } from '@/lib/plural'

const route = useRoute()
const queryClient = useQueryClient()
const authStore = useAuthStore()

const userId = computed(() => route.params.id as string)
const isOwner = computed(() => authStore.isOwner)
const isAdmin = computed(() => authStore.isAdmin)

const addRoleOpen = ref(false)
const {
  target: roleToRemove,
  open: removeRoleOpen,
  ask: askRemoveRole,
} = useConfirm<{ id: string; name: string }>()

const { data: user, isPending } = useQuery(
  computed(() =>
    getChatUserApiChatUsersUserIdGetOptions({ path: { user_id: userId.value } }),
  ),
)

const { data: roles } = useQuery(
  computed(() => ({
    ...listRolesApiRolesGetOptions({ query: { page: 1, size: 1000 } }),
    enabled: isAdmin.value,
  })),
)

/** Что этот участник делал в панели — журнал уже умеет фильтровать по актору. */
const { data: history } = useQuery(
  computed(() => ({
    ...listLogsApiLogsGetOptions({
      query: { page: 1, size: 5, actor_id: userId.value },
    }),
    enabled: isAdmin.value,
  })),
)

const availableRoles = computed(() => {
  const assigned = new Set((user.value?.roles ?? []).map((role) => role.id))
  return (roles.value?.items ?? []).filter((role) => !assigned.has(role.id))
})

const status = computed(() => {
  if (user.value?.is_owner) return { label: 'Владелец', icon: Crown, variant: 'default' as const }
  if (user.value?.is_superuser)
    return { label: 'Администратор', icon: Shield, variant: 'secondary' as const }
  return null
})

function invalidateUser() {
  queryClient.invalidateQueries({
    queryKey: getChatUserApiChatUsersUserIdGetQueryKey({ path: { user_id: userId.value } }),
  })
}

const assignRole = useMutation({
  ...assignRoleToUserApiChatUsersUserIdRolesRoleIdPostMutation(),
  onSuccess: (_data, variables) => {
    invalidateUser()
    addRoleOpen.value = false
    const name = availableRoles.value.find((role) => role.id === variables.path.role_id)?.name
    toast.success(name ? `Роль «${name}» назначена` : 'Роль назначена')
  },
  onError: () => toast.error('Не удалось назначить роль'),
})

const removeRole = useMutation({
  ...removeRoleFromUserApiChatUsersUserIdRolesRoleIdDeleteMutation(),
  onSuccess: () => {
    invalidateUser()
    toast.success(`Роль «${roleToRemove.value?.name}» снята`)
  },
  onError: () => toast.error('Не удалось снять роль'),
})

const updateUser = useMutation({
  ...updateChatUserApiChatUsersUserIdPatchMutation(),
  onSuccess: (_data, variables) => {
    invalidateUser()
    toast.success(
      variables.body.is_superuser ? 'Права администратора выданы' : 'Права администратора сняты',
    )
  },
  onError: () => toast.error('Не удалось изменить права'),
})

function toggleAdmin(value: boolean) {
  updateUser.mutate({ path: { user_id: userId.value }, body: { is_superuser: value } })
}

function confirmRemoveRole() {
  if (!roleToRemove.value) return
  removeRole.mutate({ path: { user_id: userId.value, role_id: roleToRemove.value.id } })
}
</script>

<template>
  <div class="space-y-8">
    <PageHeader :title="user?.display_name ?? userId" :description="null">
      <template #badges>
        <Badge v-if="status" :variant="status.variant">
          <component :is="status.icon" />
          {{ status.label }}
        </Badge>
        <Badge v-if="user?.is_bot" variant="outline">
          <Bot />
          Бот
        </Badge>
      </template>
      <template #actions>
        <div
          v-if="isOwner && user && !user.is_owner"
          class="flex items-center gap-2 rounded-lg border px-3 py-2"
        >
          <Switch
            id="admin"
            :model-value="user.is_superuser"
            :disabled="updateUser.isPending.value"
            @update:model-value="toggleAdmin"
          />
          <Label for="admin" class="text-sm font-normal">Администратор</Label>
        </div>
      </template>
      <template #below>
        <CopyableId v-if="user && user.display_name !== user.id" :value="user.id" class="mt-2" />
      </template>
    </PageHeader>

    <div v-if="isPending" class="space-y-4">
      <Skeleton class="h-6 w-40" />
      <Skeleton class="h-24 w-full" />
    </div>

    <template v-else-if="user">
      <PageSection title="Роли" description="Упоминание #роли в чате призывает всех её участников">
        <template v-if="isAdmin" #actions>
          <Popover v-model:open="addRoleOpen">
            <PopoverTrigger as-child>
              <Button variant="outline" size="sm" :disabled="!availableRoles.length">
                <Plus class="size-4" />
                Назначить роль
              </Button>
            </PopoverTrigger>
            <PopoverContent class="w-64 p-0" align="end">
              <Command>
                <CommandInput placeholder="Найти роль" />
                <CommandList>
                  <CommandEmpty>Роли не нашлось</CommandEmpty>
                  <CommandGroup>
                    <CommandItem
                      v-for="role in availableRoles"
                      :key="role.id"
                      :value="role.name"
                      @select="
                        assignRole.mutate({
                          path: { user_id: userId, role_id: role.id },
                        })
                      "
                    >
                      {{ role.name }}
                    </CommandItem>
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </template>

        <div v-if="user.roles.length" class="flex flex-wrap gap-2">
          <span
            v-for="role in user.roles"
            :key="role.id"
            class="inline-flex items-center gap-1 rounded-full border bg-secondary/50 py-0.5 pl-3 pr-1 text-sm"
          >
            <RouterLink :to="`/roles/${role.id}`" class="hover:underline">
              {{ role.name }}
            </RouterLink>
            <button
              v-if="isAdmin"
              type="button"
              class="rounded-full p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
              :aria-label="`Снять роль ${role.name}`"
              @click="askRemoveRole({ id: role.id, name: role.name })"
            >
              <X class="size-3" />
            </button>
          </span>
        </div>
        <p v-else class="text-sm text-muted-foreground">Ролей нет.</p>
      </PageSection>

      <PageSection
        title="Чаты"
        :description="`Состоит в ${user.chats.length} ${plural(user.chats.length, 'чате', 'чатах', 'чатах')}`"
      >
        <ul v-if="user.chats.length" class="divide-y rounded-lg border">
          <li
            v-for="chat in user.chats"
            :key="chat.id"
            class="flex items-center justify-between gap-3 px-4 py-2.5"
          >
            <div class="flex min-w-0 items-center gap-3">
              <MessagesSquare class="size-4 shrink-0 text-muted-foreground" />
              <div class="min-w-0">
                <RouterLink
                  :to="`/chats/${chat.id}`"
                  class="block truncate text-sm font-medium hover:underline"
                >
                  {{ chat.title || chat.id }}
                </RouterLink>
                <CopyableId v-if="chat.title" :value="chat.id" />
              </div>
            </div>
            <Badge variant="outline">{{ chatTypeLabel(chat.type) }}</Badge>
          </li>
        </ul>
        <p v-else class="text-sm text-muted-foreground">
          Бот не видел этого участника ни в одном чате.
        </p>
      </PageSection>

      <PageSection v-if="isAdmin" title="Последние действия">
        <template #actions>
          <Button variant="ghost" size="sm" as-child>
            <RouterLink :to="{ path: '/logs', query: { actor_id: userId } }">
              В журнале
            </RouterLink>
          </Button>
        </template>
        <ul v-if="history?.items.length" class="divide-y">
          <li
            v-for="entry in history.items"
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
          </li>
        </ul>
        <p v-else class="text-sm text-muted-foreground">Через панель ничего не менял.</p>
      </PageSection>
    </template>

    <AlertDialog v-model:open="removeRoleOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Снять роль «{{ roleToRemove?.name }}»?</AlertDialogTitle>
          <AlertDialogDescription>
            Участник перестанет получать призывы по этой роли. Назначить её снова можно
            в любой момент.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction @click="confirmRemoveRole">Снять роль</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
