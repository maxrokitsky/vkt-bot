<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import CommandPalette from '@/components/layout/CommandPalette.vue'
import PageContainer from '@/components/layout/PageContainer.vue'

const route = useRoute()

/** Ширину задаёт сам маршрут: таблицам — размах, формам — узкая колонка. */
const width = computed(() => route.meta.width ?? 'wide')
</script>

<template>
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset class="min-w-0">
      <AppHeader />
      <main class="flex-1">
        <PageContainer :width="width">
          <RouterView />
        </PageContainer>
      </main>
    </SidebarInset>
    <CommandPalette />
  </SidebarProvider>
</template>
