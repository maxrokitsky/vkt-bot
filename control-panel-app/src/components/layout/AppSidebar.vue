<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bot } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { navGroups } from '@/router/nav'
import NavUser from '@/components/layout/NavUser.vue'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

/** Меню собирается из маршрутов — второго списка пунктов не существует. */
const groups = computed(() => navGroups(router.getRoutes(), { isAdmin: authStore.isAdmin }))

/** Подсветка держится и на дочерних страницах: `/roles/:id` светит «Роли». */
function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<template>
  <Sidebar collapsible="offcanvas" variant="inset">
    <SidebarHeader>
      <div class="flex items-center gap-2.5 px-2 py-1.5">
        <div
          class="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground"
        >
          <Bot class="size-4" />
        </div>
        <div class="flex min-w-0 flex-col leading-tight">
          <span class="truncate text-sm font-semibold">VKT Bot</span>
          <span class="truncate text-xs text-muted-foreground">Панель управления</span>
        </div>
      </div>
    </SidebarHeader>
    <SidebarContent>
      <SidebarGroup v-for="group in groups" :key="group.id">
        <SidebarGroupLabel v-if="group.label">{{ group.label }}</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="item in group.items" :key="item.path">
              <SidebarMenuButton as-child :tooltip="item.title" :is-active="isActive(item.path)">
                <RouterLink :to="item.path">
                  <component :is="item.icon" />
                  <span>{{ item.title }}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
    <SidebarFooter>
      <NavUser />
    </SidebarFooter>
  </Sidebar>
</template>
