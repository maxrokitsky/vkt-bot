<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { onKeyStroke } from '@vueuse/core'
import { LogOut, Moon, Sun } from 'lucide-vue-next'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { useAuthStore } from '@/stores/auth'
import { navGroups } from '@/router/nav'
import { useCommandPalette } from '@/composables/useCommandPalette'
import { useTheme } from '@/composables/useTheme'

const { open, toggle, hide } = useCommandPalette()
const router = useRouter()
const authStore = useAuthStore()
const { isDark, toggle: toggleTheme } = useTheme()

const groups = computed(() =>
  navGroups(router.getRoutes(), { isAdmin: authStore.isAdmin }),
)

onKeyStroke('k', (event) => {
  if (!event.metaKey && !event.ctrlKey) return
  event.preventDefault()
  toggle()
})

function run(action: () => void) {
  hide()
  action()
}
</script>

<template>
  <CommandDialog v-model:open="open" title="Поиск по панели" description="Переход к странице">
    <CommandInput placeholder="Куда перейти?" />
    <CommandList>
      <CommandEmpty>Ничего не нашлось</CommandEmpty>
      <CommandGroup
        v-for="group in groups"
        :key="group.id"
        :heading="group.label ?? 'Панель'"
      >
        <CommandItem
          v-for="item in group.items"
          :key="item.path"
          :value="[item.title, ...item.keywords].join(' ')"
          @select="run(() => router.push(item.path))"
        >
          <component :is="item.icon" class="size-4 text-muted-foreground" />
          {{ item.title }}
        </CommandItem>
      </CommandGroup>
      <CommandSeparator />
      <CommandGroup heading="Прочее">
        <CommandItem value="тема оформления светлая тёмная" @select="run(toggleTheme)">
          <Sun v-if="isDark" class="size-4 text-muted-foreground" />
          <Moon v-else class="size-4 text-muted-foreground" />
          Переключить тему
        </CommandItem>
        <CommandItem
          value="выйти выход logout"
          @select="run(() => { authStore.logout(); router.push('/login') })"
        >
          <LogOut class="size-4 text-muted-foreground" />
          Выйти
        </CommandItem>
      </CommandGroup>
    </CommandList>
  </CommandDialog>
</template>
