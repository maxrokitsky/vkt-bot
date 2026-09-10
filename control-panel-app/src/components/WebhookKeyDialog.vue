<script setup lang="ts">
import { computed } from 'vue'
import { useClipboard } from '@vueuse/core'
import { Check, Copy, TriangleAlert } from 'lucide-vue-next'
import type { WebhookResponse } from '@/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

/**
 * Ключ показывается один раз — на сервере лежит только хэш. Поэтому здесь
 * предупреждение и готовый пример запроса, а не просто строка.
 */
const props = defineProps<{
  issued: { webhook: WebhookResponse; apiKey: string } | null
  url: string
}>()

const emit = defineEmits<{ close: [] }>()

const { copy, copied } = useClipboard({ legacy: true })

const snippet = computed(
  () => `curl -X POST ${props.url} \\
  -H 'Authorization: Bearer ${props.issued?.apiKey ?? ''}' \\
  -H 'Content-Type: application/json' \\
  -d '{"text": "Сборка прошла"}'`,
)
</script>

<template>
  <Dialog :open="issued !== null" @update:open="emit('close')">
    <DialogContent class="sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>Ключ вебхука «{{ issued?.webhook.name }}»</DialogTitle>
        <DialogDescription>
          Скопируйте ключ сейчас — панель больше его не покажет.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <code
            class="min-w-0 flex-1 truncate rounded-md border bg-muted/40 px-3 py-2 font-mono text-sm"
          >
            {{ issued?.apiKey }}
          </code>
          <Button variant="outline" size="icon" aria-label="Скопировать ключ" @click="copy(issued?.apiKey ?? '')">
            <Check v-if="copied" class="size-4" />
            <Copy v-else class="size-4" />
          </Button>
        </div>

        <Alert>
          <TriangleAlert />
          <AlertTitle>Ключ хранится только у вас</AlertTitle>
          <AlertDescription>
            На сервере остаётся лишь его хэш. Если ключ потеряется, придётся выпустить
            новый — старый при этом перестанет работать.
          </AlertDescription>
        </Alert>

        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <p class="text-sm font-medium">Как вызвать</p>
            <Button variant="ghost" size="sm" @click="copy(snippet)">
              <Copy class="size-3.5" />
              Скопировать
            </Button>
          </div>
          <pre
            class="overflow-x-auto rounded-md border bg-muted/40 p-3 font-mono text-xs"
          >{{ snippet }}</pre>
        </div>
      </div>

      <DialogFooter>
        <Button @click="emit('close')">Готово</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
