<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronsUpDown, Crown, LogOut, Moon, Shield, Sun } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import UserAvatar from '@/components/data/UserAvatar.vue'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { useTheme } from '@/composables/useTheme'

const { isMobile } = useSidebar()
const router = useRouter()
const authStore = useAuthStore()

const { isDark, toggle: toggleTheme } = useTheme()

/** Имя приходит из `/api/auth/me`; до ответа сервера показываем нейтральное. */
const name = computed(() => authStore.user?.display_name ?? 'Профиль')
const userId = computed(() => authStore.user?.id ?? '')
const role = computed(() => {
  if (authStore.user?.is_owner) return { label: 'Владелец', icon: Crown }
  if (authStore.user?.is_superuser) return { label: 'Администратор', icon: Shield }
  return null
})

const photoUrl = computed(() => authStore.user?.photo_url ?? null)

function logout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <SidebarMenu>
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <SidebarMenuButton
            size="lg"
            class="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
          >
            <UserAvatar :name="name" :src="photoUrl" />
            <div class="grid flex-1 text-left leading-tight">
              <span class="truncate text-sm font-medium">{{ name }}</span>
              <span class="truncate text-xs text-muted-foreground">
                {{ role?.label ?? userId }}
              </span>
            </div>
            <ChevronsUpDown class="ml-auto size-4" />
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          class="w-(--reka-dropdown-menu-trigger-width) min-w-56 rounded-lg"
          :side="isMobile ? 'bottom' : 'right'"
          :side-offset="4"
          align="end"
        >
          <DropdownMenuLabel class="font-normal">
            <div class="space-y-1">
              <p class="truncate text-sm font-medium">{{ name }}</p>
              <p class="truncate font-mono text-xs text-muted-foreground">{{ userId }}</p>
              <p v-if="role" class="flex items-center gap-1.5 text-xs text-muted-foreground">
                <component :is="role.icon" class="size-3" />
                {{ role.label }}
              </p>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem @click="toggleTheme">
            <Sun v-if="isDark" />
            <Moon v-else />
            Переключить тему
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem @click="logout">
            <LogOut />
            Выйти
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  </SidebarMenu>
</template>
