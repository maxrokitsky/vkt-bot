<script setup lang="ts">
import { computed, useSlots } from 'vue'
import { useRoute } from 'vue-router'

/**
 * Единственный `h1` страницы. Название по умолчанию берётся из маршрута,
 * чтобы обычным страницам не приходилось его дублировать.
 */
const props = defineProps<{
  title?: string
  description?: string | null
  /** Убрать нижний отступ, если сразу под шапкой идёт свой блок. */
  tight?: boolean
}>()

const route = useRoute()
const slots = useSlots()

const title = computed(() => props.title ?? route.meta.title ?? '')
const description = computed(() =>
  props.description === undefined ? route.meta.description : props.description,
)
</script>

<template>
  <header :class="tight ? 'mb-4' : 'mb-6'">
    <div class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div class="min-w-0 space-y-1">
        <div class="flex min-w-0 items-center gap-2">
          <h1 class="truncate text-2xl font-semibold tracking-tight">{{ title }}</h1>
          <slot name="badges" />
        </div>
        <p v-if="description" class="max-w-prose text-sm text-muted-foreground">
          {{ description }}
        </p>
      </div>
      <div v-if="slots.actions" class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <slot name="below" />
  </header>
</template>
