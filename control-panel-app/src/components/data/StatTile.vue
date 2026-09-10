<script setup lang="ts">
import type { Component } from 'vue'

/** Плитка обзора. Без карточки: сетка разделяется правилами. */
defineProps<{
  label: string
  value: number | string | null | undefined
  hint?: string | null
  icon?: Component
  loading?: boolean
}>()

const formatter = new Intl.NumberFormat('ru-RU')

function format(value: number | string | null | undefined) {
  if (value === null || value === undefined) return '—'
  return typeof value === 'number' ? formatter.format(value) : value
}
</script>

<template>
  <div class="flex flex-col gap-1 px-4 py-4 sm:px-6">
    <div class="flex items-center gap-1.5 text-sm text-muted-foreground">
      <component :is="icon" v-if="icon" class="size-3.5" />
      {{ label }}
    </div>
    <div
      class="text-2xl font-semibold tabular-nums"
      :class="loading ? 'animate-pulse text-muted-foreground/40' : ''"
    >
      {{ loading ? '—' : format(value) }}
    </div>
    <p v-if="hint && !loading" class="text-xs text-muted-foreground">{{ hint }}</p>
  </div>
</template>
