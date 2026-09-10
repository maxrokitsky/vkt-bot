<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/**
 * Панель сохранения, которая появляется только при несохранённых правках,
 * — чтобы кнопка «Сохранить» не висела на странице без причины.
 */
const props = withDefaults(
  defineProps<{
    dirty: boolean
    pending?: boolean
    saveLabel?: string
  }>(),
  { saveLabel: 'Сохранить изменения' },
)

const emit = defineEmits<{ save: []; reset: [] }>()
</script>

<template>
  <Transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="translate-y-2 opacity-0"
    leave-active-class="transition duration-100 ease-in"
    leave-to-class="translate-y-2 opacity-0"
  >
    <div
      v-if="dirty"
      class="sticky bottom-4 z-10 flex items-center justify-between gap-4 rounded-lg border bg-background/95 px-4 py-3 shadow-sm backdrop-blur"
    >
      <p class="text-sm text-muted-foreground">Есть несохранённые изменения</p>
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="sm" :disabled="props.pending" @click="emit('reset')">
          Отменить
        </Button>
        <Button size="sm" :disabled="props.pending" @click="emit('save')">
          <Spinner v-if="props.pending" class="size-4" />
          {{ props.saveLabel }}
        </Button>
      </div>
    </div>
  </Transition>
</template>
