import { describe, expect, it } from 'vitest'

import {
  CURRENCY_SYMBOL,
  THIN_SPACE as T,
  formatAge,
  formatCount,
  formatDateRange,
  formatDelta,
  formatIsoDate,
  formatIsoDateTime,
  formatMoney,
  formatMoneyShort,
  formatMonthFull,
  formatMonthShort,
  formatNumber,
  formatPercent,
  formatQuantity,
  isNegative,
  todayIso,
} from '@/composables/useMoneyFormat'

describe('форматирование денег', () => {
  it('делит разряды тонким пробелом и печатает копейки', () => {
    expect(formatMoney(1234567.89)).toBe(`1${T}234${T}567,89${T}${CURRENCY_SYMBOL}`)
  })

  it('добивает копейки до двух знаков', () => {
    expect(formatMoney(1500)).toBe(`1${T}500,00${T}${CURRENCY_SYMBOL}`)
  })

  it('сохраняет минус у отрицательных сумм', () => {
    expect(formatMoney(-1500.5)).toBe(`-1${T}500,50${T}${CURRENCY_SYMBOL}`)
    expect(isNegative(-1500.5)).toBe(true)
    expect(isNegative(0)).toBe(false)
  })

  it('умеет печатать без знака валюты', () => {
    expect(formatMoney(1234.5, { withCurrency: false })).toBe(`1${T}234,50`)
  })

  it('вместо отсутствующего значения показывает прочерк, а не ноль', () => {
    expect(formatMoney(null)).toBe('—')
    expect(formatMoney(undefined)).toBe('—')
    expect(formatMoney(Number.NaN)).toBe('—')
    expect(formatMoney(0)).toBe(`0,00${T}${CURRENCY_SYMBOL}`)
  })

  it('не оставляет неразрывных пробелов из Intl — только тонкие', () => {
    expect(formatMoney(1234567.89)).not.toMatch(/[\u00a0\u202f]/)
    expect(formatNumber(1234567.89)).toBe(`1${T}234${T}567,89`)
  })
})

describe('компактная запись крупных сумм', () => {
  it('миллионы и миллиарды', () => {
    expect(formatMoneyShort(1234567.89)).toBe(`1,23 млн${T}${CURRENCY_SYMBOL}`)
    expect(formatMoneyShort(3000000)).toBe(`3 млн${T}${CURRENCY_SYMBOL}`)
    expect(formatMoneyShort(-2500000)).toBe(`-2,5 млн${T}${CURRENCY_SYMBOL}`)
    expect(formatMoneyShort(1500000000)).toBe(`1,5 млрд${T}${CURRENCY_SYMBOL}`)
  })

  it('суммы меньше миллиона показывает целиком', () => {
    expect(formatMoneyShort(500000)).toBe(`500${T}000,00${T}${CURRENCY_SYMBOL}`)
  })

  it('отсутствующее значение — прочерк', () => {
    expect(formatMoneyShort(null)).toBe('—')
  })
})

describe('проценты и количества', () => {
  it('проценты — с тонким пробелом перед знаком', () => {
    expect(formatPercent(24)).toBe(`24,0${T}%`)
    expect(formatPercent(11.11, 2)).toBe(`11,11${T}%`)
    expect(formatPercent(null)).toBe('—')
  })

  it('отклонение печатается со знаком', () => {
    expect(formatDelta(11.11)).toBe(`+11,1${T}%`)
    expect(formatDelta(-8)).toBe(`-8,0${T}%`)
    expect(formatDelta(0)).toBe(`0,0${T}%`)
    expect(formatDelta(null)).toBe('—')
  })

  it('количества без дробной части и с долями', () => {
    expect(formatCount(1520)).toBe(`1${T}520`)
    expect(formatQuantity(128.5)).toBe('128,5')
    expect(formatQuantity(128.5, 0)).toBe('129')
  })
})

describe('даты, месяцы и возраст данных', () => {
  it('дата и момент времени', () => {
    expect(formatIsoDate('2026-10-11')).toBe('11.10.2026')
    expect(formatIsoDateTime('2026-10-11T07:40:03')).toBe('11.10.2026 07:40:03')
    expect(formatIsoDate(null)).toBe('—')
    expect(formatIsoDate('мусор')).toBe('—')
  })

  it('диапазон периода', () => {
    expect(formatDateRange('2026-10-01', '2026-10-11')).toBe('01.10.2026 — 11.10.2026')
  })

  it('подписи месяцев', () => {
    expect(formatMonthShort('2025-11')).toBe('ноя 25')
    expect(formatMonthFull('2026-10')).toBe('Октябрь 2026')
    expect(formatMonthShort('2026-13')).toBe('—')
  })

  it('возраст данных в понятных единицах', () => {
    expect(formatAge(42)).toBe('42 с')
    expect(formatAge(300)).toBe('5 мин')
    expect(formatAge(6003)).toBe('2 ч')
    expect(formatAge(null)).toBe('—')
  })

  it('сегодняшняя дата — в формате контракта', () => {
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
