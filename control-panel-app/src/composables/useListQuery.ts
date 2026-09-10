import { ref, watch } from 'vue'
import { refDebounced } from '@vueuse/core'

/**
 * Состояние страницы-списка: страница, размер и поиск с задержкой.
 * Ввод в поиске сбрасывает страницу — иначе «ничего не найдено» на 3-й
 * странице выглядит как пустой результат.
 */
export function useListQuery({ size = 20, debounce = 300 } = {}) {
  const page = ref(1)
  const pageSize = ref(size)
  const searchInput = ref('')
  const search = refDebounced(searchInput, debounce)

  watch(search, () => {
    page.value = 1
  })

  return { page, pageSize, searchInput, search }
}
