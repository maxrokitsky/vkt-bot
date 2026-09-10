<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { Pencil, Plus, ShieldCheck, Trash2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import type { RoleResponse } from '@/client'
import {
  createRoleApiRolesPostMutation,
  deleteRoleApiRolesRoleIdDeleteMutation,
  listRolesApiRolesGetOptions,
  listRolesApiRolesGetQueryKey,
  updateRoleApiRolesRoleIdPatchMutation,
} from '@/client/@tanstack/vue-query.gen'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/layout/PageHeader.vue'
import DataTableShell from '@/components/data/DataTableShell.vue'
import TablePagination from '@/components/data/TablePagination.vue'
import RowActions from '@/components/data/RowActions.vue'
import RoleFormDialog from '@/components/RoleFormDialog.vue'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem, DropdownMenuSeparator } from '@/components/ui/dropdown-menu'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
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
import { useConfirm } from '@/composables/useConfirm'
import { useListQuery } from '@/composables/useListQuery'
import { plural } from '@/lib/plural'

const router = useRouter()
const queryClient = useQueryClient()
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)
const { page, pageSize } = useListQuery()

/** `null` — диалог закрыт, объект без id — создание, с id — переименование. */
const editing = ref<{ id?: string; name: string } | null>(null)
const {
  target: roleToDelete,
  open: deleteRoleOpen,
  ask: askDeleteRole,
} = useConfirm<RoleResponse>()

const { data, isPending, isError, refetch } = useQuery(
  computed(() => listRolesApiRolesGetOptions({ query: { page: page.value, size: pageSize.value } })),
)

function invalidate() {
  queryClient.invalidateQueries({ queryKey: listRolesApiRolesGetQueryKey() })
}

const createRole = useMutation({
  ...createRoleApiRolesPostMutation(),
  onSuccess: (role) => {
    invalidate()
    editing.value = null
    toast.success(`Роль «${role.name}» создана`)
  },
  onError: () => toast.error('Роль с таким названием уже есть'),
})

const renameRole = useMutation({
  ...updateRoleApiRolesRoleIdPatchMutation(),
  onSuccess: (role) => {
    invalidate()
    editing.value = null
    toast.success(`Роль переименована в «${role.name}»`)
  },
  onError: () => toast.error('Роль с таким названием уже есть'),
})

const deleteRole = useMutation({
  ...deleteRoleApiRolesRoleIdDeleteMutation(),
  onSuccess: () => {
    invalidate()
    toast.success(`Роль «${roleToDelete.value?.name}» удалена`)
  },
  onError: () => toast.error('Не удалось удалить роль'),
})

function submit(name: string) {
  const role = editing.value
  if (!role) return
  if (role.id) renameRole.mutate({ path: { role_id: role.id }, body: { name } })
  else createRole.mutate({ body: { name } })
}
</script>

<template>
  <div>
    <PageHeader>
      <template v-if="isAdmin" #actions>
        <Button size="sm" @click="editing = { name: '' }">
          <Plus class="size-4" />
          Новая роль
        </Button>
      </template>
    </PageHeader>

    <DataTableShell
      :loading="isPending"
      :error="isError ? true : undefined"
      :empty="!data?.items.length"
      :columns="isAdmin ? 3 : 2"
      :empty-icon="ShieldCheck"
      empty-title="Ролей пока нет"
      empty-description="Роль — это группа участников, которую можно призвать в чате через #название."
      @retry="refetch()"
    >
      <template #empty-action>
        <Button v-if="isAdmin" @click="editing = { name: '' }">
          <Plus class="size-4" />
          Новая роль
        </Button>
      </template>

      <template #header>
        <TableHeader>
          <TableRow>
            <TableHead>Роль</TableHead>
            <TableHead class="w-40">Участников</TableHead>
            <TableHead v-if="isAdmin" class="w-16 text-right">
              <span class="sr-only">Действия</span>
            </TableHead>
          </TableRow>
        </TableHeader>
      </template>

      <template #body>
        <TableBody>
          <TableRow
            v-for="role in data?.items ?? []"
            :key="role.id"
            class="cursor-pointer"
            @click="router.push(`/roles/${role.id}`)"
          >
            <TableCell>
              <span class="font-medium">{{ role.name }}</span>
              <span class="ml-2 font-mono text-xs text-muted-foreground">#{{ role.name }}</span>
            </TableCell>
            <TableCell class="tabular-nums">
              {{ role.member_count ?? 0 }}
              <span class="text-muted-foreground">
                {{ plural(role.member_count ?? 0, 'участник', 'участника', 'участников') }}
              </span>
            </TableCell>
            <TableCell v-if="isAdmin" class="text-right">
              <RowActions>
                <DropdownMenuItem @click="editing = { id: role.id, name: role.name }">
                  <Pencil />
                  Переименовать
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" @click="askDeleteRole(role)">
                  <Trash2 />
                  Удалить
                </DropdownMenuItem>
              </RowActions>
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
      items-label="ролей"
      @update:page="page = $event"
    />

    <RoleFormDialog
      :role="editing"
      :pending="createRole.isPending.value || renameRole.isPending.value"
      @submit="submit"
      @close="editing = null"
    />

    <AlertDialog v-model:open="deleteRoleOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить роль «{{ roleToDelete?.name }}»?</AlertDialogTitle>
          <AlertDialogDescription>
            Роль исчезнет у всех
            {{ roleToDelete?.member_count ?? 0 }}
            {{
              plural(roleToDelete?.member_count ?? 0, 'участника', 'участников', 'участников')
            }}, и призыв #{{ roleToDelete?.name }} перестанет работать. Отменить нельзя.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            @click="roleToDelete && deleteRole.mutate({ path: { role_id: roleToDelete.id } })"
          >
            Удалить роль
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
