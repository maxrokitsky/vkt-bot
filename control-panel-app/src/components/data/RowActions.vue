<script setup lang="ts">
import { MoreHorizontal } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

/** Действия строки в одном меню: ряд кнопок в каждой строке — главный шум. */
defineProps<{ label?: string }>()
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button
        variant="ghost"
        size="icon"
        class="size-8 text-muted-foreground data-[state=open]:bg-accent"
        :aria-label="label ?? 'Действия'"
      >
        <MoreHorizontal class="size-4" />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" class="w-48">
      <slot />
    </DropdownMenuContent>
  </DropdownMenu>
</template>
