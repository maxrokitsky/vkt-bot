<script setup lang="ts">
import { useSlots } from 'vue'

/**
 * Раздел страницы: заголовок с правилом-разделителем вместо карточки.
 * Так группировка видна, но страница не рассыпается на плитки.
 */
defineProps<{
  title?: string
  description?: string
}>()

const slots = useSlots()
</script>

<template>
  <section class="space-y-4">
    <div
      v-if="title || slots.actions"
      class="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b pb-2"
    >
      <div class="space-y-1">
        <h2 v-if="title" class="text-sm font-semibold">{{ title }}</h2>
        <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>
      </div>
      <div v-if="slots.actions" class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </section>
</template>
