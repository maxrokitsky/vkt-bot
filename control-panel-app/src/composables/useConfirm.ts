import { ref, shallowRef } from 'vue'

/**
 * Состояние подтверждающего диалога: что подтверждаем и открыт ли он.
 *
 * Флаг открытости отдельный от цели не случайно. `AlertDialogAction` — это
 * ещё и `DialogClose`, и его собственный обработчик закрытия срабатывает
 * раньше нашего `@click`. Со связкой `:open="target !== null"` плюс
 * `@update:open="target = null"` цель обнулялась до того, как до неё
 * доходило действие, и кнопка подтверждения молча ничего не делала. Здесь
 * закрытие цель не трогает: она живёт до следующего `ask()`, поэтому её
 * видят и обработчик кнопки, и `onSuccess` мутации.
 */
export function useConfirm<T>() {
  const target = shallowRef<T | null>(null)
  const open = ref(false)

  /** Спросить подтверждение для этой цели. */
  function ask(value: T) {
    target.value = value
    open.value = true
  }

  return { target, open, ask }
}
