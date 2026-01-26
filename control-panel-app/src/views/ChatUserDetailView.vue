<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
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
import { ArrowLeft, Plus, Shield, Crown } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { useAuthStore } from '@/stores/auth'
import {
  getChatUserApiChatUsersUserIdGetOptions,
  getChatUserApiChatUsersUserIdGetQueryKey,
  listRolesApiRolesGetOptions,
  assignRoleToUserApiChatUsersUserIdRolesRoleIdPostMutation,
  removeRoleFromUserApiChatUsersUserIdRolesRoleIdDeleteMutation,
  updateChatUserApiChatUsersUserIdPatchMutation,
} from '@/client/@tanstack/vue-query.gen'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.isOwner)
const userId = computed(() => route.params.id as string)
const showAddRoleDialog = ref(false)
const selectedRoleId = ref<string>('')
const showDeleteRoleDialog = ref(false)
const roleToDelete = ref<{ id: string; name: string } | null>(null)

const { data: userData, isLoading } = useQuery(
  computed(() => getChatUserApiChatUsersUserIdGetOptions({
    path: { user_id: userId.value },
  }))
)

const { data: rolesData } = useQuery(
  listRolesApiRolesGetOptions({
    query: { page: 1, size: 1000 },
  })
)

const assignRoleMutation = useMutation({
  ...assignRoleToUserApiChatUsersUserIdRolesRoleIdPostMutation(),
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: getChatUserApiChatUsersUserIdGetQueryKey({
        path: { user_id: userId.value },
      }),
    })
    showAddRoleDialog.value = false
    selectedRoleId.value = ''
  },
})

const removeRoleMutation = useMutation({
  ...removeRoleFromUserApiChatUsersUserIdRolesRoleIdDeleteMutation(),
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: getChatUserApiChatUsersUserIdGetQueryKey({
        path: { user_id: userId.value },
      }),
    })
  },
})

const updateUserMutation = useMutation({
  ...updateChatUserApiChatUsersUserIdPatchMutation(),
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: getChatUserApiChatUsersUserIdGetQueryKey({
        path: { user_id: userId.value },
      }),
    })
    toast.success('Статус администратора обновлен')
  },
  onError: (error) => {
    toast.error(`Ошибка: ${error.message}`)
  },
})

const handleAssignRole = () => {
  if (selectedRoleId.value) {
    assignRoleMutation.mutate({
      path: { user_id: userId.value, role_id: selectedRoleId.value },
    })
  }
}

const handleRemoveRole = (roleId: string, roleName: string) => {
  roleToDelete.value = { id: roleId, name: roleName }
  showDeleteRoleDialog.value = true
}

const confirmRemoveRole = () => {
  if (roleToDelete.value) {
    removeRoleMutation.mutate({
      path: { user_id: userId.value, role_id: roleToDelete.value.id },
    })
    showDeleteRoleDialog.value = false
    roleToDelete.value = null
  }
}

const goBack = () => {
  router.push('/chat-users')
}

const handleToggleAdmin = (checked: boolean) => {
  updateUserMutation.mutate({
    path: { user_id: userId.value },
    body: { is_superuser: checked },
  })
}

// Доступные роли для добавления (исключая уже назначенные)
const availableRoles = computed(() => {
  if (!rolesData.value?.items || !userData.value) return []
  const userRoleIds = new Set(userData.value.roles.map(r => r.id))
  return rolesData.value.items.filter(role => !userRoleIds.has(role.id))
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

    <!-- Статус администратора -->
    <div v-if="!isLoading && userData" class="flex items-center gap-4 p-4 border rounded-lg">
      <div class="flex items-center gap-2">
        <Badge v-if="userData.is_owner" variant="default" class="gap-1">
          <Crown class="h-3 w-3" />
          Владелец
        </Badge>
        <Badge v-else-if="userData.is_superuser" variant="secondary" class="gap-1">
          <Shield class="h-3 w-3" />
          Админ
        </Badge>
        <span v-else class="text-sm text-muted-foreground">Обычный пользователь</span>
      </div>
      <div v-if="isOwner && !userData.is_owner" class="flex items-center gap-2 ml-auto">
        <Switch
          :checked="userData.is_superuser"
          :disabled="updateUserMutation.isPending.value"
          @update:checked="handleToggleAdmin"
        />
        <Label class="text-sm">Администратор</Label>
      </div>
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
