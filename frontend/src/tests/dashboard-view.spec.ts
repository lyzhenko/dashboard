import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { http, HttpResponse } from 'msw'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { AntComponents } from '@/app/plugins'
import DashboardView from '@/views/DashboardView.vue'
import { THIN_SPACE as T } from '@/composables/useMoneyFormat'
import { API, emptySummary, sampleSummary, server, staleSummary } from './handlers'

async function mountDashboard(options: { settle?: boolean } = {}): Promise<VueWrapper> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: DashboardView },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
    ],
  })
  await router.push('/')
  await router.isReady()

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  const wrapper = mount(DashboardView, {
    global: {
      plugins: [createPinia(), router, AntComponents, [VueQueryPlugin, { queryClient }]],
    },
  })

  if (options.settle !== false) {
    await flushPromises()
  }
  return wrapper
}

describe('DashboardView — главный экран', () => {
  it('показывает KPI, период и свежесть данных', async () => {
    const wrapper = await mountDashboard()

    await vi.waitFor(
      () => {
        expect(wrapper.text()).toContain('1,23 млн')
      },
      { timeout: 5000 },
    )

    const text = wrapper.text()
    // деньги, выручка, прибыль, портфель заказов
    expect(text).toContain('Деньги')
    expect(text).toContain('Выручка за период')
    expect(text).toContain('+11,1')
    expect(text).toContain('Валовая прибыль')
    expect(text).toContain('Портфель заказов')
    // заказы: главное число — портфель, детали рядом
    expect(text).toContain(`900${T}000,00`)
    expect(text).toContain('Единиц к отгрузке')
    expect(text).toContain('128,5')
    expect(text).toContain('К отгрузке на неделе')
    // выручка без НДС вместо прежнего «с НДС»
    expect(text).toContain('Без НДС')
    // корзины по возрасту долга
    expect(text).toContain('0–7 дней')
    expect(text).toContain('Свыше 60 дней')
    // период и предыдущий период видны пользователю
    expect(text).toContain('Месяц · 01.10.2026 — 11.10.2026')
    expect(text).toContain('Предыдущий: 01.09.2026 — 11.09.2026')
    // свежесть данных
    expect(text).toContain('данные свежие')
    expect(text).toContain('обновлено 11.10.2026 07:40:03')
    // селектор организаций: явный пункт «Все организации» выбран по умолчанию
    expect(text).toContain('Все организации')
    // топ-5
    expect(text).toContain('Топ-5 должников')
    expect(text).toContain('ООО «Василёк»')
  })

  it('при meta.stale показывает плашку «данные устарели»', async () => {
    server.use(http.get(`${API}/dashboard/summary`, () => HttpResponse.json(staleSummary)))

    const wrapper = await mountDashboard()

    await vi.waitFor(
      () => {
        expect(wrapper.find('[data-testid="stale-banner"]').exists()).toBe(true)
      },
      { timeout: 5000 },
    )

    expect(wrapper.get('[data-testid="stale-banner"]').text()).toContain('Данные устарели')
    expect(wrapper.text()).toContain('данные устарели')
  })

  it('нули на пустой базе — это «данных за период нет», а не ошибка', async () => {
    server.use(http.get(`${API}/dashboard/summary`, () => HttpResponse.json(emptySummary)))

    const wrapper = await mountDashboard()

    await vi.waitFor(
      () => {
        expect(wrapper.find('[data-testid="empty-notice"]').exists()).toBe(true)
      },
      { timeout: 5000 },
    )

    expect(wrapper.text()).toContain('Данных за период нет')
    expect(wrapper.find('[data-testid="error-block"]').exists()).toBe(false)
    expect(wrapper.text()).toContain(`0,00${T}₽`)
  })

  it('при 503 kpi_unavailable показывает сообщение и кнопку «Повторить»', async () => {
    server.use(
      http.get(`${API}/dashboard/summary`, () =>
        HttpResponse.json(
          {
            detail: {
              code: 'kpi_unavailable',
              message: 'Данные 1С недоступны: превышено время ожидания',
            },
          },
          { status: 503 },
        ),
      ),
    )

    const wrapper = await mountDashboard()

    await vi.waitFor(
      () => {
        expect(wrapper.find('[data-testid="error-block"]').exists()).toBe(true)
      },
      { timeout: 5000 },
    )

    const block = wrapper.get('[data-testid="error-block"]')
    expect(block.text()).toContain('Данные 1С недоступны')
    expect(block.text()).toContain('превышено время ожидания')
    expect(block.text()).toContain('Повторить')
  })

  it('кнопка «Обновить» перечитывает данные из 1С и обновляет индикатор свежести', async () => {
    const refreshed = {
      ...sampleSummary,
      meta: { ...sampleSummary.meta, fetchedAt: '2026-10-11T09:00:00', ageSeconds: 1 },
    }
    server.use(http.post(`${API}/dashboard/refresh`, () => HttpResponse.json(refreshed)))

    const wrapper = await mountDashboard()
    await vi.waitFor(
      () => {
        expect(wrapper.text()).toContain('обновлено 11.10.2026 07:40:03')
      },
      { timeout: 5000 },
    )

    await wrapper.get('[data-testid="refresh"]').trigger('click')
    await flushPromises()

    await vi.waitFor(
      () => {
        expect(wrapper.text()).toContain('обновлено 11.10.2026 09:00:00')
      },
      { timeout: 5000 },
    )
    expect(wrapper.text()).toContain('1 с назад')
  })

  it('загрузка показывает скелетоны, а не прочерки', async () => {
    // без ожидания ответа сервера: проверяем самый первый кадр
    const wrapper = await mountDashboard({ settle: false })

    expect(wrapper.findAll('.ant-skeleton').length).toBeGreaterThan(0)

    await vi.waitFor(
      () => {
        expect(wrapper.text()).toContain('1,23 млн')
      },
      { timeout: 5000 },
    )
    expect(wrapper.findAll('.ant-skeleton').length).toBe(0)
  })
})
