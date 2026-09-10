import { computed } from 'vue'
import { useColorMode } from '@vueuse/core'

type ColorMode = ReturnType<typeof useColorMode>

/**
 * Тема — одна на всё приложение.
 *
 * Отдельные вызовы `useColorMode` с одним ключом внутри одного документа не
 * синхронизируются между собой, поэтому экземпляр создаётся один раз (первый
 * вызов — из `App.vue`, до любого маршрута). Иначе класс `dark` не появлялся
 * на странице входа, где сайдбара с переключателем нет.
 */
let mode: ColorMode | null = null

export function useTheme() {
  mode ??= useColorMode({ attribute: 'class', modes: { light: 'light', dark: 'dark' } })
  const colorMode = mode

  return {
    colorMode,
    isDark: computed(() => colorMode.value === 'dark'),
    toggle: () => {
      colorMode.value = colorMode.value === 'dark' ? 'light' : 'dark'
    },
  }
}
