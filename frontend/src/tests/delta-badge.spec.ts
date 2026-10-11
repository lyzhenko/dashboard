import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DeltaBadge from '@/components/DeltaBadge.vue'
import { THIN_SPACE as T } from '@/composables/useMoneyFormat'

describe('DeltaBadge — отклонение от прошлого периода', () => {
  it('рост показывается зелёным со знаком плюс', () => {
    const wrapper = mount(DeltaBadge, { props: { value: 11.11 } })

    expect(wrapper.text()).toContain(`+11,1${T}%`)
    expect(wrapper.classes()).toContain('delta--up')
    expect(wrapper.text()).toContain('▲')
  })

  it('падение показывается красным со знаком минус', () => {
    const wrapper = mount(DeltaBadge, { props: { value: -8 } })

    expect(wrapper.text()).toContain(`-8,0${T}%`)
    expect(wrapper.classes()).toContain('delta--down')
    expect(wrapper.text()).toContain('▼')
  })

  it('ноль не выдаётся за рост: прочерк и нейтральный вид', () => {
    const wrapper = mount(DeltaBadge, { props: { value: 0 } })

    expect(wrapper.text()).toBe('—')
    expect(wrapper.text()).not.toContain('+')
    expect(wrapper.classes()).toContain('delta--unknown')
    expect(wrapper.classes()).not.toContain('delta--up')
  })

  it('без базы сравнения (null) — прочерк и подсказка', () => {
    const wrapper = mount(DeltaBadge, { props: { value: null } })

    expect(wrapper.text()).toBe('—')
    expect(wrapper.classes()).toContain('delta--unknown')
    expect(wrapper.attributes('title')).toContain('Нет базы сравнения')
  })

  it('нулевое отклонение можно показать числом, если это нужно явно', () => {
    const wrapper = mount(DeltaBadge, { props: { value: 0, zeroAsDash: false } })

    expect(wrapper.text()).toContain(`0,0${T}%`)
    expect(wrapper.classes()).toContain('delta--flat')
  })
})
