<script setup lang="ts">
import { RouterView } from 'vue-router'
import 'vue-sonner/style.css'
import { Toaster } from '@/components/ui/sonner'
import { useTheme } from '@/composables/useTheme'

// Тему поднимаем здесь, чтобы класс `dark` стоял на всех страницах, включая вход.
useTheme()
</script>

<template>
  <RouterView />
  <Toaster />
</template>
