<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'

/** Один диалог на создание и переименование: поля у них одинаковые. */
const props = defineProps<{
  role: { id?: string; name: string } | null
  pending?: boolean
}>()

const emit = defineEmits<{ submit: [string]; close: [] }>()

const name = ref('')

watch(
  () => props.role,
  (role) => {
    if (role) name.value = role.name
  },
  { immediate: true },
)
</script>

<template>
  <Dialog :open="role !== null" @update:open="emit('close')">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{{ role?.id ? 'Переименовать роль' : 'Новая роль' }}</DialogTitle>
        <DialogDescription>
          Название — то, что пишут в чате после решётки: #{{ name.trim() || 'название' }}
        </DialogDescription>
      </DialogHeader>

      <form class="space-y-2" @submit.prevent="emit('submit', name.trim())">
        <Label for="role-name">Название</Label>
        <Input
          id="role-name"
          v-model="name"
          autofocus
          required
          :disabled="pending"
          placeholder="devs"
        />
      </form>

      <DialogFooter>
        <Button variant="ghost" :disabled="pending" @click="emit('close')">Отмена</Button>
        <Button :disabled="!name.trim() || pending" @click="emit('submit', name.trim())">
          <Spinner v-if="pending" class="size-4" />
          {{ role?.id ? 'Сохранить' : 'Создать роль' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
