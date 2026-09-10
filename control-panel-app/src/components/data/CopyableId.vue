<script setup lang="ts">
import { computed, ref } from 'vue'
import { useClipboard } from '@vueuse/core'
import { Check, Copy } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

/**
 * Идентификатор: моношириной, укороченный, с копированием.
 * Полные id в таблице — шум, но они нужны для поддержки, поэтому копируется
 * всегда целиком.
 */
const props = withDefaults(
  defineProps<{ value: string; max?: number; class?: string }>(),
  { max: 28 },
)

const { copy, copied, isSupported } = useClipboard({ legacy: true })
const hovered = ref(false)

const shown = computed(() =>
  props.value.length > props.max ? `${props.value.slice(0, props.max - 1)}…` : props.value,
)
</script>

<template>
  <span
    :class="cn('inline-flex max-w-full items-center gap-1', props.class)"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
  >
    <span class="truncate font-mono text-xs text-muted-foreground" :title="value">
      {{ shown }}
    </span>
    <button
      v-if="isSupported"
      type="button"
      class="rounded p-0.5 text-muted-foreground transition-opacity hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      :class="hovered || copied ? 'opacity-100' : 'opacity-0'"
      :aria-label="`Скопировать ${value}`"
      @click.stop.prevent="copy(value)"
    >
      <Check v-if="copied" class="size-3" />
      <Copy v-else class="size-3" />
    </button>
  </span>
</template>
