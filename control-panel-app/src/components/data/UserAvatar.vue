<script setup lang="ts">
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { initials } from '@/lib/users'
import { cn } from '@/lib/utils'

/**
 * Аватар участника: картинка из профиля, а если её нет — инициалы.
 *
 * Ссылку приносит `chats/getInfo` (поле `photo`), и она открывается без
 * авторизации, поэтому идёт прямо в `src`. Но само поле приходит всегда, а
 * картинки за ссылкой может и не быть — `AvatarImage` в этом случае
 * молча уступает место `AvatarFallback`, ради чего он тут и нужен.
 */
const props = defineProps<{ name: string; src?: string | null; class?: string }>()
</script>

<template>
  <Avatar :class="cn('size-8 rounded-md', props.class)">
    <AvatarImage v-if="src" :src="src" :alt="name" class="rounded-md" />
    <AvatarFallback class="rounded-md text-xs">{{ initials(name) }}</AvatarFallback>
  </Avatar>
</template>
