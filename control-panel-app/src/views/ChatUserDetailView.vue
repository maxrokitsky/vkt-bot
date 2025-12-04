<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  TagsInput,
  TagsInputItem,
  TagsInputItemDelete,
  TagsInputItemText,
} from '@/components/ui/tags-input'
import { ArrowLeft, Plus } from 'lucide-vue-next'

// Временные типы, пока не сгенерирован клиент
interface ChatUserRole {
  id: string
  name: string
}

interface ChatUserChat {
  id: string
  type: string
}

interface ChatUserDetail {
  id: string
  roles: ChatUserRole[]
  chats: ChatUserChat[]
}

interface Role {
  id: string
  name: string
}

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const userId = computed(() => route.params.id as string)
const showAddRoleDialog = ref(false)
const selectedRoleId = ref<string>('')
const showDeleteRoleDialog = ref(false)
const roleToDelete = ref<{ id: string; name: string } | null>(null)

const getToken = () => localStorage.getItem('token')

// Функция для загрузки деталей пользователя
const fetchChatUserDetail = async (userId: string): Promise<ChatUserDetail> => {
  const token = getToken()
  const response = await fetch(`http://localhost:8000/api/chat-users/${userId}`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })
  if (!response.ok) {
    throw new Error('Failed to fetch chat user details')
  }
  return response.json()
}

// Функция для загрузки всех ролей
const fetchRoles = async (): Promise<Role[]> => {
  const token = getToken()
  const response = await fetch('http://localhost:8000/api/roles?page=1&size=1000', {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })
  if (!response.ok) {
    throw new Error('Failed to fetch roles')
  }
  const data = await response.json()
  return data.items
}

// Функция для назначения роли
const assignRole = async (userId: string, roleId: string): Promise<void> => {
  const token = getToken()
  const response = await fetch(`http://localhost:8000/api/chat-users/${userId}/roles/${roleId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })
  if (!response.ok) {
    throw new Error('Failed to assign role')
  }
}

// Функция для удаления роли
const removeRole = async (userId: string, roleId: string): Promise<void> => {
  const token = getToken()
  const response = await fetch(`http://localhost:8000/api/chat-users/${userId}/roles/${roleId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  })
  if (!response.ok) {
    throw new Error('Failed to remove role')
  }
}

const { data: userData, isLoading } = useQuery({
  queryKey: ['chat-user', userId],
  queryFn: async () => fetchChatUserDetail(userId.value),
})

const { data: rolesData } = useQuery({
  queryKey: ['roles'],
  queryFn: fetchRoles,
})

const assignRoleMutation = useMutation({
  mutationFn: async (roleId: string) => {
    return await assignRole(userId.value, roleId)
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['chat-user', userId] })
    showAddRoleDialog.value = false
    selectedRoleId.value = ''
  },
})

const removeRoleMutation = useMutation({
  mutationFn: async (roleId: string) => {
    return await removeRole(userId.value, roleId)
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['chat-user', userId] })
  },
})

const handleAssignRole = () => {
  if (selectedRoleId.value) {
    assignRoleMutation.mutate(selectedRoleId.value)
  }
}

const handleRemoveRole = (roleId: string, roleName: string) => {
  roleToDelete.value = { id: roleId, name: roleName }
  showDeleteRoleDialog.value = true
}

const confirmRemoveRole = () => {
  if (roleToDelete.value) {
    removeRoleMutation.mutate(roleToDelete.value.id)
    showDeleteRoleDialog.value = false
    roleToDelete.value = null
  }
}

const goBack = () => {
  router.push('/chat-users')
}

// Доступные роли для добавления (исключая уже назначенные)
const availableRoles = computed(() => {
  if (!rolesData.value || !userData.value) return []
  const userRoleIds = new Set(userData.value.roles.map(r => r.id))
  return rolesData.value.filter(role => !userRoleIds.has(role.id))
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <Button variant="ghost" size="sm" @click="goBack">
        <ArrowLeft class="h-4 w-4 mr-2" />
        Назад
      </Button>
      <h1 class="text-3xl font-bold">Пользователь: {{ userId }}</h1>
    </div>

    <div v-if="!isLoading && userData" class="grid gap-6 md:grid-cols-2">
      <!-- Роли пользователя -->
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold">Роли</h2>
          <Dialog v-model:open="showAddRoleDialog">
            <DialogTrigger as-child>
              <Button size="sm">
                <Plus class="h-4 w-4 mr-2" />
                Добавить роль
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Назначить роль</DialogTitle>
              </DialogHeader>
              <div class="space-y-4">
                <div class="space-y-2">
                  <label class="text-sm font-medium">Выберите роль</label>
                  <Select v-model="selectedRoleId">
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите роль" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="role in availableRoles"
                        :key="role.id"
                        :value="role.id"
                      >
                        {{ role.name }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  @click="handleAssignRole"
                  class="w-full"
                  :disabled="!selectedRoleId || assignRoleMutation.isPending.value"
                >
                  Назначить
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        <TagsInput
          :model-value="userData.roles.map(r => r.name)"
          :disabled="removeRoleMutation.isPending.value"
        >
          <TagsInputItem
            v-for="role in userData.roles"
            :key="role.id"
            :value="role.name"
          >
            <TagsInputItemText />
            <TagsInputItemDelete @click="handleRemoveRole(role.id, role.name)" />
          </TagsInputItem>
        </TagsInput>
        <div v-if="userData.roles.length === 0" class="text-center py-4 text-sm text-muted-foreground">
          У пользователя нет ролей
        </div>
      </div>

      <!-- Чаты пользователя -->
      <div class="space-y-4">
        <h2 class="text-xl font-semibold">Чаты</h2>
        <div v-if="userData.chats.length > 0" class="space-y-2">
          <div
            v-for="chat in userData.chats"
            :key="chat.id"
            class="flex items-center justify-between p-3 border rounded-lg bg-card"
          >
            <div>
              <div class="font-medium">{{ chat.id }}</div>
              <Badge variant="outline" class="mt-1">{{ chat.type }}</Badge>
            </div>
          </div>
        </div>
        <div v-else class="text-center py-8 text-muted-foreground border rounded-lg">
          Пользователь не состоит в чатах
        </div>
      </div>
    </div>
    <div v-else class="py-8 text-center">Загрузка...</div>

    <!-- Диалог подтверждения удаления роли -->
    <AlertDialog v-model:open="showDeleteRoleDialog">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удаление роли</AlertDialogTitle>
          <AlertDialogDescription>
            Вы уверены, что хотите удалить роль "{{ roleToDelete?.name }}"?
            Это действие нельзя отменить.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction @click="confirmRemoveRole">
            Удалить
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
