<script setup lang="ts">
import { Moon, Sun } from 'lucide-vue-next'
import { useColorMode } from '@vueuse/core'
import { Button } from '@/components/ui/button'

const colorMode = useColorMode({
  attribute: 'class',
  modes: {
    light: 'light',
    dark: 'dark',
  },
})

const toggleTheme = () => {
  colorMode.value = colorMode.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <Button variant="ghost" size="icon" @click="toggleTheme" title="Переключить тему">
    <Sun v-if="colorMode === 'dark'" class="h-5 w-5" />
    <Moon v-else class="h-5 w-5" />
  </Button>
</template>
