import { config } from '@vue/test-utils'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { server } from './handlers'

/**
 * jsdom не умеет ResizeObserver и matchMedia, а Ant Design Vue их использует
 * (адаптивность, измерения выпадающих списков). Подменяем заглушками.
 */
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
}

if (typeof window !== 'undefined' && typeof window.matchMedia === 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

/**
 * Компоненты Ant Design Vue регистрируются по списку (src/app/plugins.ts), а не целиком.
 * Забытый в списке тег `a-*` в шаблоне Vue молча отрисует как неизвестный элемент,
 * поэтому такое предупреждение превращаем в ошибку теста.
 */
const unresolvedComponents: string[] = []

config.global.config.warnHandler = (message: string) => {
  if (message.includes('Failed to resolve component')) {
    unresolvedComponents.push(message)
  }
}

// В тестах нет реальных сетевых вызовов: всё перехватывает MSW,
// неописанный запрос — ошибка теста, а не «тихо прошло».
// В MSW 3 эта настройка называется onUnhandledFrame.
beforeAll(() => {
  server.listen({ onUnhandledFrame: 'error' })
})

afterEach(() => {
  server.resetHandlers()

  if (unresolvedComponents.length > 0) {
    const messages = unresolvedComponents.splice(0).join('\n')
    throw new Error(`Компонент не зарегистрирован в src/app/plugins.ts:\n${messages}`)
  }
})

afterAll(() => {
  server.close()
})
