<script setup lang="ts">
import { useSlots } from 'vue'
import { Label } from '@/components/ui/label'

/**
 * Строка настройки: подпись и пояснение слева, контрол справа.
 * Для полей во всю ширину (textarea) — вариант `stacked`.
 */
defineProps<{
  label: string
  description?: string
  for?: string
  stacked?: boolean
}>()

const slots = useSlots()
</script>

<template>
  <div
    :class="
      stacked
        ? 'space-y-2 py-4'
        : 'flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-4'
    "
  >
    <div class="space-y-1" :class="stacked ? '' : 'max-w-md'">
      <Label :for="$props.for" class="text-sm font-medium">{{ label }}</Label>
      <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>
    </div>
    <div :class="stacked ? '' : 'shrink-0'">
      <slot />
    </div>
    <p v-if="slots.hint" class="w-full text-sm text-muted-foreground">
      <slot name="hint" />
    </p>
  </div>
</template>
