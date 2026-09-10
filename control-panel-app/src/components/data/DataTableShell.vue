<script setup lang="ts">
import type { Component } from 'vue'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import EmptyState from '@/components/data/EmptyState.vue'

/**
 * Оболочка таблицы: рамка, скролл, залипающая шапка и три состояния
 * (загрузка, ошибка, пусто) в одном месте вместо «Загрузка...» в каждой вьюхе.
 */
const props = withDefaults(
  defineProps<{
    loading?: boolean
    error?: unknown
    empty?: boolean
    columns: number
    rows?: number
    emptyIcon?: Component
    emptyTitle?: string
    emptyDescription?: string
  }>(),
  { rows: 5, emptyTitle: 'Пока ничего нет' },
)

defineEmits<{ retry: [] }>()
</script>

<template>
  <Alert v-if="props.error" variant="destructive">
    <AlertTitle>Не удалось загрузить данные</AlertTitle>
    <AlertDescription>
      <p>Проверьте соединение и попробуйте снова.</p>
      <Button variant="outline" size="sm" class="mt-2" @click="$emit('retry')">
        Повторить
      </Button>
    </AlertDescription>
  </Alert>

  <EmptyState
    v-else-if="props.empty && !props.loading"
    :icon="emptyIcon"
    :title="emptyTitle"
    :description="emptyDescription"
  >
    <slot name="empty-action" />
  </EmptyState>

  <div v-else class="overflow-hidden rounded-lg border">
    <Table class="[&_thead_th]:h-10 [&_tbody_td]:py-2.5">
      <slot name="header" />
      <TableBody v-if="props.loading">
        <TableRow v-for="row in props.rows" :key="row" class="hover:bg-transparent">
          <TableCell v-for="column in props.columns" :key="column">
            <Skeleton class="h-4" :class="column === 1 ? 'w-48' : 'w-24'" />
          </TableCell>
        </TableRow>
      </TableBody>
      <slot v-else name="body" />
    </Table>
  </div>
</template>
