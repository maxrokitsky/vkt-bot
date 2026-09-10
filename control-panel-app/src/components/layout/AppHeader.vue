<script setup lang="ts">
import { Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import AppBreadcrumbs from '@/components/layout/AppBreadcrumbs.vue'
import { useCommandPalette } from '@/composables/useCommandPalette'

const { show } = useCommandPalette()
</script>

<template>
  <header
    class="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur lg:px-6"
  >
    <SidebarTrigger class="-ml-1" />
    <Separator orientation="vertical" class="mx-1 data-[orientation=vertical]:h-4" />
    <AppBreadcrumbs />
    <Button
      variant="outline"
      size="sm"
      class="ml-auto gap-2 text-muted-foreground"
      @click="show()"
    >
      <Search class="size-4" />
      <span class="hidden sm:inline">Поиск</span>
      <Kbd class="hidden sm:inline-flex">⌘K</Kbd>
    </Button>
  </header>
</template>
