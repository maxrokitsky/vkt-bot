<script setup lang="ts">
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import AppSidebar from '@/components/AppSidebar.vue'
</script>

<template>
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset>
      <header class="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b bg-background px-4">
        <SidebarTrigger class="-ml-1" />
        <Separator orientation="vertical" class="h-4" />
        <div class="flex-1" />
      </header>

      <main class="flex-1 p-6">
        <RouterView />
      </main>

      <footer class="border-t bg-muted py-4 px-6">
        <div class="text-center text-sm text-muted-foreground">
          VKT Bot Control Panel © 2025
        </div>
      </footer>
    </SidebarInset>
  </SidebarProvider>
</template>
