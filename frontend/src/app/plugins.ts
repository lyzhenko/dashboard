import type { App, Plugin } from 'vue'

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Input,
  Radio,
  Result,
  Row,
  Select,
  Skeleton,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue'
import { createPinia } from 'pinia'

import { ApiError } from '@/api/client'

export const pinia = createPinia()

/**
 * Регистрируем только те компоненты Ant Design Vue, которые встречаются в шаблонах.
 * Полное `app.use(Antd)` тянет всю библиотеку одним чанком (~1,4 МБ),
 * поэтому список поддерживается вручную: добавили тег `a-*` — добавьте компонент сюда.
 * Тесты ловят забытый компонент: в src/tests/setup.ts предупреждение
 * «Failed to resolve component» превращается в ошибку теста.
 */
const ANT_COMPONENTS: Plugin[] = [
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Input, // регистрирует и a-input, и a-input-password
  Radio, // регистрирует a-radio-group и a-radio-button
  Result,
  Row,
  Select,
  Skeleton,
  Spin,
  Tag,
  Tooltip,
] as unknown as Plugin[]

export function registerAntComponents(app: App): void {
  for (const component of ANT_COMPONENTS) {
    app.use(component)
  }
}

/** Плагин с компонентами Ant — тем же набором пользуются тесты. */
export const AntComponents: Plugin = {
  install: registerAntComponents,
}

/**
 * Настройки серверного состояния по умолчанию.
 * Данные дашборда дорогие (бэкенд опрашивает 1С), поэтому лишние перезапросы выключены:
 * обновление — по кнопке «Обновить» (POST /dashboard/refresh) или по смене параметров.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 10 * 60_000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false
          }
          return failureCount < 1
        },
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export const queryClient = createQueryClient()

/** Плагины приложения: Pinia, компоненты Ant Design Vue, TanStack Vue Query. */
export function installPlugins(app: App): void {
  app.use(pinia)
  registerAntComponents(app)
  app.use(VueQueryPlugin, { queryClient })
}
