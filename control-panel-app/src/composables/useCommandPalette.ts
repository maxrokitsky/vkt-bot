import { ref } from 'vue'

/** Открыта ли палитра команд. Общее состояние для шапки и самой палитры. */
const open = ref(false)

export function useCommandPalette() {
  return {
    open,
    toggle: () => (open.value = !open.value),
    show: () => (open.value = true),
    hide: () => (open.value = false),
  }
}
