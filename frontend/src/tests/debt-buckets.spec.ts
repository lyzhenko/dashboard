import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { AntComponents } from '@/app/plugins'
import type { DebtBucket } from '@/api/dashboard'
import DebtBuckets from '@/components/DebtBuckets.vue'
import { THIN_SPACE as T } from '@/composables/useMoneyFormat'

const buckets: DebtBucket[] = [
  { label: '0–7 дней', amount: 650000 },
  { label: '8–14 дней', amount: 50000 },
  { label: '15–30 дней', amount: 60000 },
  { label: '31–60 дней', amount: 30000 },
  { label: 'Свыше 60 дней', amount: 10000 },
]

function mountBuckets(props: { buckets: DebtBucket[] | null; total?: number | null }): VueWrapper {
  return mount(DebtBuckets, { props, global: { plugins: [AntComponents] } })
}

function widths(wrapper: VueWrapper): (string | undefined)[] {
  return wrapper.findAll('.buckets__fill').map((fill) => fill.attributes('data-width'))
}

describe('DebtBuckets — разбор корзин задолженности', () => {
  it('рисует по полосе на каждую корзину с подписью и суммой', () => {
    const wrapper = mountBuckets({ buckets, total: 800000 })

    expect(wrapper.findAll('.buckets__row')).toHaveLength(5)
    expect(wrapper.text()).toContain('0–7 дней')
    expect(wrapper.text()).toContain('Свыше 60 дней')
    expect(wrapper.text()).toContain(`650${T}000,00${T}₽`)
    expect(wrapper.text()).toContain(`10${T}000,00${T}₽`)
  })

  it('считает длину полосы от самой крупной корзины', () => {
    const wrapper = mountBuckets({ buckets, total: 800000 })

    // 650 000 — самая большая корзина, она задаёт 100 %
    expect(widths(wrapper)).toEqual(['100', '8', '9', '5', '2'])
  })

  it('показывает долю каждой корзины в итоге в процентах', () => {
    const wrapper = mountBuckets({ buckets, total: 800000 })

    const shares = wrapper.findAll('.buckets__share').map((share) => share.text())
    expect(shares).toHaveLength(5)
    expect(shares.every((share) => share.endsWith('%'))).toBe(true)
  })

  it('без итога доля не выдумывается — прочерк', () => {
    const wrapper = mountBuckets({ buckets, total: 0 })

    expect(wrapper.findAll('.buckets__share').map((share) => share.text())).toEqual([
      '—',
      '—',
      '—',
      '—',
      '—',
    ])
  })

  it('пустой список корзин — «задолженности нет», а не ошибка', () => {
    const wrapper = mountBuckets({ buckets: [] })

    expect(wrapper.text()).toContain('Задолженности нет')
    expect(wrapper.findAll('.buckets__row')).toHaveLength(0)
  })

  it('нулевые корзины тоже считаются отсутствием долга', () => {
    const wrapper = mountBuckets({ buckets: [{ label: '0–7 дней', amount: 0 }], total: 0 })

    expect(wrapper.text()).toContain('Задолженности нет')
  })

  it('отсутствующие данные не роняют компонент', () => {
    const wrapper = mountBuckets({ buckets: null })

    expect(wrapper.text()).toContain('Задолженности нет')
  })
})
