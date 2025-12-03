<script setup lang="ts">
import { computed } from 'vue'
import { IconHome, IconUsers, IconMessageCircle, IconShield, IconUsersGroup, IconWebhook } from "@tabler/icons-vue"
import { useAuthStore } from '@/stores/auth'

import NavMain from '@/components/NavMain.vue'
import NavUser from '@/components/NavUser.vue'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  // SidebarMenu,
  // SidebarMenuButton,
  // SidebarMenuItem,
} from '@/components/ui/sidebar'

const authStore = useAuthStore()

const user = computed(() => ({
  name: authStore.user?.username || 'Пользователь',
  email: authStore.user?.email || '',
  avatar: '',
}))

const isAdmin = computed(() => authStore.isAdmin)

const navMain = computed(() => [
  {
    title: "Главная",
    url: "/",
    icon: IconHome,
  },
  ...(isAdmin.value ? [{
    title: "Пользователи",
    url: "/users",
    icon: IconUsers,
  }] : []),
  {
    title: "Чаты",
    url: "/chats",
    icon: IconMessageCircle,
  },
  {
    title: "Пользователи чатов",
    url: "/chat-users",
    icon: IconUsersGroup,
  },
  {
    title: "Роли",
    url: "/roles",
    icon: IconShield,
  },
  ...(isAdmin.value ? [{
    title: "GitLab Webhooks",
    url: "/gitlab/webhooks",
    icon: IconWebhook,
  }] : []),
])
</script>

<template>
  <Sidebar collapsible="offcanvas">
    <SidebarHeader class="p-4">
      <div class="flex items-center gap-2">
        <!-- <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
          VKT
        </div> -->
        <div class="flex flex-col">
          <span class="text-sm font-semibold">VKT Bot</span>
          <span class="text-xs text-muted-foreground">Панель управления</span>
        </div>
      </div>
    </SidebarHeader>
    <SidebarContent>
      <NavMain :items="navMain" />
    </SidebarContent>
    <SidebarFooter>
      <NavUser :user="user" />
    </SidebarFooter>
  </Sidebar>
</template>
