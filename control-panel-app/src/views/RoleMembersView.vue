<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  getRoleApiRolesRoleIdGet,
  addRoleMemberApiRolesRoleIdMembersPost,
  removeRoleMemberApiRolesRoleIdMembersUserIdDelete,
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
import { Plus, Trash2, ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()
const roleId = computed(() => route.params.id as string)
const showAddDialog = ref(false)
const newUserId = ref('')

const { data: roleData, isLoading } = useQuery({
  queryKey: ['role', roleId],
  queryFn: async () => {
    const response = await getRoleApiRolesRoleIdGet({
      path: { role_id: roleId.value },
    })
    return response.data
  },
})

const addMutation = useMutation({
  mutationFn: async (userId: string) => {
    return await addRoleMemberApiRolesRoleIdMembersPost({
      path: { role_id: roleId.value },
      body: { user_id: userId },
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['role', roleId.value] })
    showAddDialog.value = false
    newUserId.value = ''
  },
})

const removeMutation = useMutation({
  mutationFn: async (userId: string) => {
    return await removeRoleMemberApiRolesRoleIdMembersUserIdDelete({
      path: { role_id: roleId.value, user_id: userId },
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['role', roleId.value] })
  },
})

const handleAdd = () => {
  addMutation.mutate(newUserId.value)
}

const handleRemove = (userId: string) => {
  if (confirm('Вы уверены, что хотите удалить этого участника из роли?')) {
    removeMutation.mutate(userId)
  }
}

const goBack = () => {
  router.push('/roles')
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <Button variant="outline" size="sm" @click="goBack">
        <ArrowLeft class="h-4 w-4" />
      </Button>
      <h1 class="text-3xl font-bold">
        Участники роли {{ roleData?.name || '...' }}
      </h1>
    </div>

    <div class="flex justify-end">
      <Dialog v-model:open="showAddDialog">
        <DialogTrigger as-child>
          <Button>
            <Plus class="mr-2 h-4 w-4" />
            Добавить участника
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить участника в роль</DialogTitle>
          </DialogHeader>
          <form @submit.prevent="handleAdd" class="space-y-4">
            <div class="space-y-2">
              <Label for="user_id">User ID</Label>
              <Input id="user_id" v-model="newUserId" required placeholder="Введите User ID" />
            </div>
            <Button type="submit" class="w-full" :disabled="addMutation.isPending.value">
              Добавить
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <Card>
      <CardContent class="pt-6">
        <Table v-if="!isLoading && roleData">
          <TableHeader>
            <TableRow>
              <TableHead>User ID</TableHead>
              <TableHead class="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="roleData.members.length === 0">
              <TableCell colspan="2" class="text-center text-muted-foreground">
                В этой роли пока нет участников
              </TableCell>
            </TableRow>
            <TableRow v-for="member in roleData.members" :key="member.user_id">
              <TableCell class="font-mono text-sm">{{ member.user_id }}</TableCell>
              <TableCell class="text-right">
                <Button
                  variant="destructive"
                  size="sm"
                  @click="handleRemove(member.user_id)"
                >
                  <Trash2 class="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div v-else class="py-8 text-center">Загрузка...</div>
      </CardContent>
    </Card>
  </div>
</template>
