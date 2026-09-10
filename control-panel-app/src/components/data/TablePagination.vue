<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'

/** Одна пагинация на все списки: раньше она была скопирована пять раз. */
const props = defineProps<{
  page: number
  size: number
  total: number
  pages: number
  /** Что считаем — «чатов», «участников». Родительный падеж. */
  itemsLabel: string
}>()

const emit = defineEmits<{ 'update:page': [number] }>()

const formatter = new Intl.NumberFormat('ru-RU')

const range = computed(() => {
  if (props.total === 0) return null
  const first = (props.page - 1) * props.size + 1
  const last = Math.min(props.page * props.size, props.total)
  return `${formatter.format(first)}–${formatter.format(last)} из ${formatter.format(props.total)} ${props.itemsLabel}`
})
</script>

<template>
  <div v-if="range" class="mt-4 flex flex-wrap items-center justify-between gap-2">
    <p class="text-sm tabular-nums text-muted-foreground">{{ range }}</p>
    <Pagination
      v-if="props.pages > 1"
      :page="props.page"
      :items-per-page="props.size"
      :total="props.total"
      :sibling-count="1"
      show-edges
      class="mx-0 w-auto justify-end"
      @update:page="emit('update:page', $event)"
    >
      <PaginationContent v-slot="{ items }">
        <PaginationPrevious>
          <ChevronLeft class="size-4" />
          <span class="sr-only">Назад</span>
        </PaginationPrevious>
        <template v-for="(item, index) in items" :key="index">
          <PaginationItem
            v-if="item.type === 'page'"
            :value="item.value"
            :is-active="item.value === props.page"
            class="tabular-nums"
          >
            {{ item.value }}
          </PaginationItem>
          <PaginationEllipsis v-else />
        </template>
        <PaginationNext>
          <ChevronRight class="size-4" />
          <span class="sr-only">Далее</span>
        </PaginationNext>
      </PaginationContent>
    </Pagination>
  </div>
</template>
