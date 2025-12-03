<script setup lang="ts">
import { ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  listUsersApiUsersGet,
  createUserApiUsersPost,
  deleteUserApiUsersUsernameDelete,
  updateUserApiUsersUsernamePatch,
  type UserResponse,
  type UserCreate,
  type UserUpdate,
} from '@/client'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
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
const selectedUser = ref<UserResponse | null>(null)
const showDeleteDialog = ref(false)
const userToDelete = ref<string | null>(null)

const newUser = ref<UserCreate>({
  username: '',
  password: '',
  is_superuser: false,
  is_active: true,
})

const editUser = ref<UserUpdate>({
  username: null,
  password: null,
  is_superuser: null,
  is_active: null,
})

const { data: usersData, isLoading } = useQuery({
  queryKey: ['users', page, size],
  queryFn: async () => {
    const response = await listUsersApiUsersGet({
      query: { page: page.value, size: size.value },
    })
    return response.data
  },
})

const createMutation = useMutation({
  mutationFn: async (user: UserCreate) => {
    return await createUserApiUsersPost({ body: user })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['users'] })
    showCreateDialog.value = false
    newUser.value = {
      username: '',
      password: '',
      is_superuser: false,
      is_active: true,
    }
  },
})

const deleteMutation = useMutation({
  mutationFn: async (username: string) => {
    return await deleteUserApiUsersUsernameDelete({
      path: { username },
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['users'] })
  },
})

const updateMutation = useMutation({
  mutationFn: async ({ username, data }: { username: string; data: UserUpdate }) => {
    return await updateUserApiUsersUsernamePatch({
      path: { username },
      body: data,
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['users'] })
    showEditDialog.value = false
    selectedUser.value = null
  },
})

const handleCreate = () => {
  createMutation.mutate(newUser.value)
}

const handleDelete = (username: string) => {
  userToDelete.value = username
  showDeleteDialog.value = true
}

const confirmDelete = () => {
  if (userToDelete.value) {
    deleteMutation.mutate(userToDelete.value)
    showDeleteDialog.value = false
    userToDelete.value = null
  }
}

const openEditDialog = (user: UserResponse) => {
  selectedUser.value = user
  editUser.value = {
    username: user.username,
    password: null,
    is_superuser: user.is_superuser,
    is_active: user.is_active,
  }
  showEditDialog.value = true
}

const handleUpdate = () => {
  if (selectedUser.value) {
    updateMutation.mutate({
      username: selectedUser.value.username,
      data: editUser.value,
    })
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-end">
      <!-- <h1 class="text-3xl font-bold">Пользователи</h1> -->
      <Dialog v-model:open="showCreateDialog">
        <DialogTrigger as-child>
          <Button>
            <Plus class="mr-2 h-4 w-4" />
            Добавить пользователя
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Создать пользователя</DialogTitle>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="username">Имя пользователя</Label>
              <Input id="username" v-model="newUser.username" required />
            </div>
            <div class="space-y-2">
              <Label for="password">Пароль</Label>
              <Input id="password" v-model="newUser.password" type="password" required />
            </div>
            <div class="flex items-center space-x-2">
              <input
                id="is_superuser"
                v-model="newUser.is_superuser"
                type="checkbox"
                class="h-4 w-4"
              />
              <Label for="is_superuser" class="cursor-pointer">Администратор</Label>
            </div>
            <div class="flex items-center space-x-2">
              <input
                id="is_active"
                v-model="newUser.is_active"
                type="checkbox"
                class="h-4 w-4"
              />
              <Label for="is_active" class="cursor-pointer">Активен</Label>
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
        <Table v-if="!isLoading && usersData">
          <TableHeader>
            <TableRow>
              <TableHead>Имя пользователя</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="user in usersData.items" :key="user.username">
              <TableCell class="font-medium">{{ user.username }}</TableCell>
              <TableCell>{{ user.email }}</TableCell>
              <TableCell>
                <Badge :variant="user.is_active ? 'default' : 'secondary'">
                  {{ user.is_active ? 'Активен' : 'Неактивен' }}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge :variant="user.is_superuser ? 'destructive' : 'outline'">
                  {{ user.is_superuser ? 'Админ' : 'Пользователь' }}
                </Badge>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="openEditDialog(user)"
                  >
                    <Edit class="h-4 w-4" />
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    @click="handleDelete(user.username)"
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

    <div v-if="usersData" class="flex items-center justify-between">
      <div class="text-sm text-muted-foreground">
        Показано {{ usersData.items.length }} из {{ usersData.total }} пользователей
      </div>
      <div class="flex gap-2">
        <Button variant="outline" :disabled="page <= 1" @click="page--">Назад</Button>
        <Button variant="outline" :disabled="page >= usersData.pages" @click="page++">
          Далее
        </Button>
      </div>
    </div>

    <Dialog v-model:open="showEditDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Редактировать пользователя</DialogTitle>
        </DialogHeader>
        <form @submit.prevent="handleUpdate" class="space-y-4">
          <div class="space-y-2">
            <Label for="edit-username">Имя пользователя</Label>
            <Input id="edit-username" v-model="editUser.username" />
          </div>
          <div class="space-y-2">
            <Label for="edit-password">Новый пароль (оставьте пустым, чтобы не менять)</Label>
            <Input id="edit-password" v-model="editUser.password" type="password" />
          </div>
          <div class="flex items-center space-x-2">
            <input
              id="edit-is_superuser"
              v-model="editUser.is_superuser"
              type="checkbox"
              class="h-4 w-4"
            />
            <Label for="edit-is_superuser" class="cursor-pointer">Администратор</Label>
          </div>
          <div class="flex items-center space-x-2">
            <input
              id="edit-is_active"
              v-model="editUser.is_active"
              type="checkbox"
              class="h-4 w-4"
            />
            <Label for="edit-is_active" class="cursor-pointer">Активен</Label>
          </div>
          <Button type="submit" class="w-full" :disabled="updateMutation.isPending.value">
            Сохранить
          </Button>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Диалог подтверждения удаления пользователя -->
    <AlertDialog v-model:open="showDeleteDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удаление пользователя</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите удалить пользователя "{{ userToDelete }}"?
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
