import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { AntComponents } from '@/app/plugins'
import StaleBanner from '@/components/StaleBanner.vue'

describe('StaleBanner — плашка «данные устарели»', () => {
  it('при meta.stale = true показывает предупреждение, время и возраст данных', () => {
    const wrapper = mount(StaleBanner, {
      props: { stale: true, fetchedAt: '2026-10-11T06:00:00', ageSeconds: 6003 },
      global: { plugins: [AntComponents] },
    })

    const text = wrapper.get('[data-testid="stale-banner"]').text()
    expect(text).toContain('Данные устарели')
    expect(text).toContain('11.10.2026 06:00:00')
    expect(text).toContain('2 ч')
    expect(text).toContain('Обновить')
  })

  it('при свежих данных плашки нет', () => {
    const wrapper = mount(StaleBanner, {
      props: { stale: false, fetchedAt: '2026-10-11T07:40:03', ageSeconds: 42 },
      global: { plugins: [AntComponents] },
    })

    expect(wrapper.find('[data-testid="stale-banner"]').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('кнопка «Обновить» сообщает наверх о необходимости перечитать данные', async () => {
    const wrapper = mount(StaleBanner, {
      props: { stale: true, fetchedAt: '2026-10-11T06:00:00', ageSeconds: 6003 },
      global: { plugins: [AntComponents] },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('refresh')).toHaveLength(1)
  })
})
