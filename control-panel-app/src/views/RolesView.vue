<script setup lang="ts">
import { ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  listRolesApiRolesGet,
  createRoleApiRolesPost,
  deleteRoleApiRolesRoleIdDelete,
  updateRoleApiRolesRoleIdPatch,
  type RoleCreate,
  type RoleUpdate,
  type RoleResponse,
} from '@/client'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { Plus, Trash2, Edit } from 'lucide-vue-next'

const queryClient = useQueryClient()
const page = ref(1)
const size = ref(10)
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const selectedRole = ref<RoleResponse | null>(null)
const showDeleteDialog = ref(false)
const roleToDelete = ref<string | null>(null)

const newRole = ref<RoleCreate>({
  name: '',
})

const editRole = ref<RoleUpdate>({
  name: null,
})

const { data: rolesData, isLoading } = useQuery({
  queryKey: ['roles', page, size],
  queryFn: async () => {
    const response = await listRolesApiRolesGet({
      query: { page: page.value, size: size.value },
    })
    return response.data
  },
})

const createMutation = useMutation({
  mutationFn: async (role: RoleCreate) => {
    return await createRoleApiRolesPost({ body: role })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['roles'] })
    showCreateDialog.value = false
    newRole.value = { name: '' }
  },
})

const deleteMutation = useMutation({
  mutationFn: async (roleId: string) => {
    return await deleteRoleApiRolesRoleIdDelete({
      path: { role_id: roleId },
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['roles'] })
  },
})

const updateMutation = useMutation({
  mutationFn: async ({ roleId, data }: { roleId: string; data: RoleUpdate }) => {
    return await updateRoleApiRolesRoleIdPatch({
      path: { role_id: roleId },
      body: data,
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['roles'] })
    showEditDialog.value = false
    selectedRole.value = null
  },
})

const handleCreate = () => {
  createMutation.mutate(newRole.value)
}

const handleDelete = (roleId: string) => {
  roleToDelete.value = roleId
  showDeleteDialog.value = true
}

const confirmDelete = () => {
  if (roleToDelete.value) {
    deleteMutation.mutate(roleToDelete.value)
    showDeleteDialog.value = false
    roleToDelete.value = null
  }
}

const openEditDialog = (role: RoleResponse) => {
  selectedRole.value = role
  editRole.value = { name: role.name }
  showEditDialog.value = true
}

const handleUpdate = () => {
  if (selectedRole.value) {
    updateMutation.mutate({
      roleId: selectedRole.value.id,
      data: editRole.value,
    })
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-end">
      <!-- <h1 class="text-3xl font-bold">Роли</h1> -->
      <Dialog v-model:open="showCreateDialog">
        <DialogTrigger as-child>
          <Button>
            <Plus class="mr-2 h-4 w-4" />
            Добавить роль
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Создать роль</DialogTitle>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="name">Название роли</Label>
              <Input id="name" v-model="newRole.name" required />
            </div>
            <Button type="submit" class="w-full" :disabled="createMutation.isPending.value">
              Создать
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <!-- <Card>
      <CardContent class="pt-6"> -->
        <Table v-if="!isLoading && rolesData">
          <TableHeader>
            <TableRow>
              <TableHead>Название</TableHead>
              <TableHead>ID</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="role in rolesData.items" :key="role.id">
              <TableCell class="font-medium">{{ role.name }}</TableCell>
              <TableCell class="font-mono text-sm">{{ role.id }}</TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="openEditDialog(role)"
                  >
                    <Edit class="h-4 w-4" />
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    @click="handleDelete(role.id)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div v-else class="py-8 text-center">Загрузка...</div>
      <!-- </CardContent>
    </Card> -->

    <div v-if="rolesData" class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Показано {{ rolesData.items.length }} из {{ rolesData.total }} ролей
      </div>
      <div class="flex gap-2">
        <Button variant="outline" :disabled="page <= 1" @click="page--">Назад</Button>
        <Button variant="outline" :disabled="page >= rolesData.pages" @click="page++">
          Далее
        </Button>
      </div>
    </div>

    <Dialog v-model:open="showEditDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Редактировать роль</DialogTitle>
        </DialogHeader>
        <form @submit.prevent="handleUpdate" class="space-y-4">
          <div class="space-y-2">
            <Label for="edit-name">Название роли</Label>
            <Input id="edit-name" v-model="editRole.name" />
          </div>
          <Button type="submit" class="w-full" :disabled="updateMutation.isPending.value">
            Сохранить
          </Button>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Диалог подтверждения удаления роли -->
    <AlertDialog v-model:open="showDeleteDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удаление роли</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите удалить эту роль?
            Это действие нельзя отменить.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction @click="confirmDelete">
            Удалить
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
