<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { Bot, Pencil, Plus, Trash2, UserMinus, Users } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import {
  addRoleMemberApiRolesRoleIdMembersPostMutation,
  deleteRoleApiRolesRoleIdDeleteMutation,
  getRoleApiRolesRoleIdGetOptions,
  getRoleApiRolesRoleIdGetQueryKey,
  listChatUsersApiChatUsersGetOptions,
  removeRoleMemberApiRolesRoleIdMembersUserIdDeleteMutation,
  updateRoleApiRolesRoleIdPatchMutation,
} from '@/client/@tanstack/vue-query.gen'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import PageSection from '@/components/layout/PageSection.vue'
import CopyableId from '@/components/data/CopyableId.vue'
import EmptyState from '@/components/data/EmptyState.vue'
import RoleFormDialog from '@/components/RoleFormDialog.vue'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
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
import { useConfirm } from '@/composables/useConfirm'
import { useListQuery } from '@/composables/useListQuery'
import { plural } from '@/lib/plural'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const authStore = useAuthStore()

const roleId = computed(() => route.params.id as string)
const isAdmin = computed(() => authStore.isAdmin)

const addOpen = ref(false)
const renaming = ref<{ id: string; name: string } | null>(null)
const confirmDelete = ref(false)
const {
  target: memberToRemove,
  open: removeMemberOpen,
  ask: askRemoveMember,
} = useConfirm<{ user_id: string; display_name: string }>()

/**
 * Поиск участника идёт на сервер — список может быть большим. Локальный фильтр
 * `Command` при этом остаётся: поэтому value элемента содержит и имя, и id,
 * иначе он отбросил бы найденное сервером.
 */
const { searchInput, search } = useListQuery({ debounce: 250 })

const { data: role, isPending } = useQuery(
  computed(() => getRoleApiRolesRoleIdGetOptions({ path: { role_id: roleId.value } })),
)

const { data: candidates, isFetching: candidatesFetching } = useQuery(
  computed(() => ({
    ...listChatUsersApiChatUsersGetOptions({
      query: { page: 1, size: 20, search: search.value || undefined },
    }),
    enabled: addOpen.value && isAdmin.value,
  })),
)

const available = computed(() => {
  const members = new Set((role.value?.members ?? []).map((member) => member.user_id))
  return (candidates.value?.items ?? []).filter((user) => !members.has(user.id))
})

function invalidateRole() {
  queryClient.invalidateQueries({
    queryKey: getRoleApiRolesRoleIdGetQueryKey({ path: { role_id: roleId.value } }),
  })
}

const addMember = useMutation({
  ...addRoleMemberApiRolesRoleIdMembersPostMutation(),
  onSuccess: (member) => {
    invalidateRole()
    searchInput.value = ''
    toast.success(`${member.display_name} добавлен в роль`)
  },
  onError: () => toast.error('Не удалось добавить участника'),
})

const removeMember = useMutation({
  ...removeRoleMemberApiRolesRoleIdMembersUserIdDeleteMutation(),
  onSuccess: () => {
    invalidateRole()
    toast.success(`${memberToRemove.value?.display_name} убран из роли`)
  },
  onError: () => toast.error('Не удалось убрать участника'),
})

const renameRole = useMutation({
  ...updateRoleApiRolesRoleIdPatchMutation(),
  onSuccess: (updated) => {
    invalidateRole()
    renaming.value = null
    toast.success(`Роль переименована в «${updated.name}»`)
  },
  onError: () => toast.error('Роль с таким названием уже есть'),
})

const deleteRole = useMutation({
  ...deleteRoleApiRolesRoleIdDeleteMutation(),
  onSuccess: () => {
    toast.success(`Роль «${role.value?.name}» удалена`)
    router.push('/roles')
  },
  onError: () => toast.error('Не удалось удалить роль'),
})

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
  <div class="space-y-8">
    <PageHeader
      :title="role?.name ?? 'Роль'"
      :description="
        role
          ? `Призыв #${role.name} в чате упомянет ${role.members.length} ${plural(role.members.length, 'участника', 'участников', 'участников')}`
          : null
      "
    >
      <template v-if="isAdmin && role" #actions>
        <Button
          variant="outline"
          size="sm"
          @click="renaming = { id: role.id, name: role.name }"
        >
          <Pencil class="size-4" />
          Переименовать
        </Button>
        <Button variant="outline" size="sm" @click="confirmDelete = true">
          <Trash2 class="size-4" />
          Удалить
        </Button>
      </template>
    </PageHeader>

    <div v-if="isPending" class="space-y-3">
      <Skeleton class="h-5 w-40" />
      <Skeleton class="h-32 w-full" />
    </div>

    <PageSection v-else-if="role" title="Участники">
      <template v-if="isAdmin" #actions>
        <Popover v-model:open="addOpen">
          <PopoverTrigger as-child>
            <Button variant="outline" size="sm">
              <Plus class="size-4" />
              Добавить
            </Button>
          </PopoverTrigger>
          <PopoverContent class="w-80 p-0" align="end">
            <Command>
              <CommandInput v-model="searchInput" placeholder="Имя, ник или id" />
              <CommandList>
                <CommandEmpty>
                  {{ candidatesFetching ? 'Ищем…' : 'Никого не нашлось' }}
                </CommandEmpty>
                <CommandGroup>
                  <CommandItem
                    v-for="user in available"
                    :key="user.id"
                    :value="`${user.display_name} ${user.id}`"
                    @select="
                      addMember.mutate({
                        path: { role_id: roleId },
                        body: { user_id: user.id },
                      })
                    "
                  >
                    <div class="min-w-0">
                      <div class="truncate">{{ user.display_name }}</div>
                      <div
                        v-if="user.display_name !== user.id"
                        class="truncate font-mono text-xs text-muted-foreground"
                      >
                        {{ user.id }}
                      </div>
                    </div>
                  </CommandItem>
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </template>

      <ul v-if="role.members.length" class="divide-y rounded-lg border">
        <li
          v-for="member in role.members"
          :key="member.user_id"
          class="flex items-center justify-between gap-3 px-4 py-2.5"
        >
          <RouterLink
            :to="`/chat-users/${member.user_id}`"
            class="flex min-w-0 items-center gap-3 hover:underline"
          >
            <Avatar class="size-8 rounded-md">
              <AvatarFallback class="rounded-md text-xs">
                {{ initials(member.display_name) }}
              </AvatarFallback>
            </Avatar>
            <div class="min-w-0">
              <div class="truncate text-sm font-medium">{{ member.display_name }}</div>
              <CopyableId
                v-if="member.display_name !== member.user_id"
                :value="member.user_id"
              />
            </div>
          </RouterLink>
          <div class="flex shrink-0 items-center gap-2">
            <Badge v-if="member.is_bot" variant="outline">
              <Bot />
              Бот
            </Badge>
            <Button
              v-if="isAdmin"
              variant="ghost"
              size="icon"
              class="size-8 text-muted-foreground"
              :aria-label="`Убрать ${member.display_name} из роли`"
              @click="askRemoveMember(member)"
            >
              <UserMinus class="size-4" />
            </Button>
          </div>
        </li>
      </ul>

      <EmptyState
        v-else
        :icon="Users"
        title="В роли никого нет"
        description="Пока роль пуста, призыв в чате ничего не сделает."
      >
        <Button v-if="isAdmin" @click="addOpen = true">
          <Plus class="size-4" />
          Добавить участника
        </Button>
      </EmptyState>
    </PageSection>

    <RoleFormDialog
      :role="renaming"
      :pending="renameRole.isPending.value"
      @submit="(name) => renaming && renameRole.mutate({ path: { role_id: renaming.id }, body: { name } })"
      @close="renaming = null"
    />

    <AlertDialog v-model:open="confirmDelete">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить роль «{{ role?.name }}»?</AlertDialogTitle>
          <AlertDialogDescription>
            Роль исчезнет у всех участников, и призыв #{{ role?.name }} перестанет
            работать. Отменить нельзя.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction @click="deleteRole.mutate({ path: { role_id: roleId } })">
            Удалить роль
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <AlertDialog v-model:open="removeMemberOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Убрать {{ memberToRemove?.display_name }} из роли?
          </AlertDialogTitle>
          <AlertDialogDescription>
            Участник перестанет получать призывы по этой роли.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="
              memberToRemove &&
                removeMember.mutate({
                  path: { role_id: roleId, user_id: memberToRemove.user_id },
                })
            "
          >
            Убрать
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
