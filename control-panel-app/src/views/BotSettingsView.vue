<script setup lang="ts">
import { ref, computed } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  getBotSettingApiBotSettingsKeyGet,
  updateBotSettingApiBotSettingsKeyPut,
  type UpdateBotSettingsRequest,
} from '@/client'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Save } from 'lucide-vue-next'

const queryClient = useQueryClient()
const startMessageKey = 'start_message'

const editedValue = ref('')

const { data: startMessageData, isLoading } = useQuery({
  queryKey: ['bot-setting', startMessageKey],
  queryFn: async () => {
    try {
      const response = await getBotSettingApiBotSettingsKeyGet({
        path: { key: startMessageKey },
      })
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null
      }
      throw error
    }
  },
})

const updateMutation = useMutation({
  mutationFn: async (data: UpdateBotSettingsRequest) => {
    return await updateBotSettingApiBotSettingsKeyPut({
      path: { key: startMessageKey },
      body: data,
    })
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['bot-setting', startMessageKey] })
  },
})

const displayValue = computed(() => {
  if (editedValue.value !== '') {
    return editedValue.value
  }
  return startMessageData.value?.value || ''
})

const hasChanges = computed(() => {
  if (!startMessageData.value) {
    return editedValue.value !== ''
  }
  return editedValue.value !== startMessageData.value.value
})

const handleSave = () => {
  updateMutation.mutate({
    value: displayValue.value,
  })
}

const resetChanges = () => {
  editedValue.value = ''
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="isLoading" class="py-8 text-center">Загрузка...</div>

    <div v-else class="space-y-4">
      <div class="space-y-2">
        <Label for="start-message">Текст команды /start</Label>
        <Textarea
          id="start-message"
          v-model="editedValue"
          :placeholder="
            startMessageData?.value || 'Введите текст приветственного сообщения'
          "
          rows="15"
          class="font-mono text-sm"
        />
        <p class="text-sm text-muted-foreground">
          Поддерживается форматирование MarkdownV2. Используйте экранирование для
          специальных символов.
        </p>
      </div>

      <div class="flex gap-2">
        <Button
          @click="handleSave"
          :disabled="!hasChanges || updateMutation.isPending.value"
        >
          <Save class="mr-2 h-4 w-4" />
          {{ updateMutation.isPending.value ? 'Сохранение...' : 'Сохранить' }}
        </Button>
        <Button variant="outline" @click="resetChanges" :disabled="!hasChanges">
          Отменить
        </Button>
      </div>

      <div
        v-if="updateMutation.isSuccess.value"
        class="p-4 rounded-md bg-green-50 text-green-800 border border-green-200"
      >
        Настройки успешно сохранены
      </div>

      <div
        v-if="updateMutation.isError.value"
        class="p-4 rounded-md bg-red-50 text-red-800 border border-red-200"
      >
        Ошибка при сохранении: {{ updateMutation.error.value }}
      </div>
    </div>
  </div>
</template>
