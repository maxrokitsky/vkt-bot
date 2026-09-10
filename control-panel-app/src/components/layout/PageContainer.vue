<script setup lang="ts">
import { computed } from 'vue'
import type { PageWidth } from '@/router/nav'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<{ width?: PageWidth; class?: string }>(), {
  width: 'wide',
})

/**
 * Контент не растягивается на всю ширину: у таблиц свой предел, у форм —
 * строка короче 80 знаков, иначе её неудобно читать.
 */
const widths: Record<PageWidth, string> = {
  narrow: 'max-w-[42rem]',
  medium: 'max-w-4xl',
  wide: 'max-w-[84rem]',
}

const widthClass = computed(() => widths[props.width])
</script>

<template>
  <div :class="cn('mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8', widthClass, props.class)">
    <slot />
  </div>
</template>
