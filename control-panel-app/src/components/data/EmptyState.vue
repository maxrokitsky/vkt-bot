<script setup lang="ts">
import type { Component } from 'vue'
import { useSlots } from 'vue'
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'

/**
 * Пустой экран — приглашение к действию, а не сообщение об отсутствии данных.
 * Поэтому у него всегда есть объяснение и, по возможности, кнопка.
 */
defineProps<{
  icon?: Component
  title: string
  description?: string
}>()

const slots = useSlots()
</script>

<template>
  <Empty class="border">
    <EmptyHeader>
      <EmptyMedia v-if="icon" variant="icon">
        <component :is="icon" />
      </EmptyMedia>
      <EmptyTitle>{{ title }}</EmptyTitle>
      <EmptyDescription v-if="description">{{ description }}</EmptyDescription>
    </EmptyHeader>
    <EmptyContent v-if="slots.default">
      <slot />
    </EmptyContent>
  </Empty>
</template>
