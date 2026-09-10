<script setup lang="ts">
import { useSlots } from 'vue'
import { Search } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'

/**
 * Полоса над таблицей: поиск, фильтры, действия. Одинаковая на всех списках.
 * Счётчик найденного живёт в пагинации — здесь он дублировался бы.
 */
const props = defineProps<{
  search?: string
  placeholder?: string
}>()

defineEmits<{ 'update:search': [string] }>()

const slots = useSlots()
</script>

<template>
  <div class="mb-4 flex flex-wrap items-center gap-2">
    <div v-if="props.search !== undefined" class="relative w-full sm:w-72">
      <Search
        class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        :model-value="props.search"
        :placeholder="placeholder ?? 'Поиск'"
        class="pl-9"
        @update:model-value="$emit('update:search', String($event))"
      />
    </div>
    <slot name="filters" />
    <div v-if="slots.actions" class="ml-auto flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
