/**
 * Форматирование денег, процентов и дат по-русски.
 *
 * Правила проекта:
 *  - Intl.NumberFormat('ru-RU'), разделитель разрядов — тонкий пробел (U+2009), копейки — запятая;
 *  - деньги всегда с «₽»; отрицательные значения компоненты красят своим цветом;
 *  - пустое значение (null/undefined/NaN) — прочерк «—», а не «0»: ноль и «нет данных» — разное.
 */

/** Тонкий пробел — разделитель разрядов и отбивка перед знаком валюты/процента. */
export const THIN_SPACE = '\u2009'

export const CURRENCY_SYMBOL = '₽'

/** Что показывает Intl для ru-RU: неразрывный (U+00A0) и узкий неразрывный (U+202F) пробелы. */
const ANY_SPACE = /[\u00a0\u202f\u2009]/g

const MISSING = '—'

const decimalCache = new Map<number, Intl.NumberFormat>()

function decimalFormatter(fractionDigits: number): Intl.NumberFormat {
  let formatter = decimalCache.get(fractionDigits)
  if (!formatter) {
    formatter = new Intl.NumberFormat('ru-RU', {
      style: 'decimal',
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    })
    decimalCache.set(fractionDigits, formatter)
  }
  return formatter
}

/** Число без валюты, но с тонкими пробелами: 1 234 567,89 */
export function formatNumber(value: number, fractionDigits = 2): string {
  return decimalFormatter(fractionDigits).format(value).replace(ANY_SPACE, THIN_SPACE)
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export interface MoneyFormatOptions {
  /** Добавлять «₽» (по умолчанию да). */
  withCurrency?: boolean
  /** Знаков после запятой (по умолчанию 2 — копейки). */
  fractionDigits?: number
}

/** 1234567.89 → «1 234 567,89 ₽»; null → «—»; -1500 → «-1 500,00 ₽». */
export function formatMoney(
  value: number | null | undefined,
  options: MoneyFormatOptions = {},
): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  const { withCurrency = true, fractionDigits = 2 } = options
  const text = formatNumber(value, fractionDigits)
  return withCurrency ? `${text}${THIN_SPACE}${CURRENCY_SYMBOL}` : text
}

/**
 * Компактная запись для крупных цифр на карточках:
 * 1 234 567,89 → «1,23 млн ₽», 3 000 000 → «3 млн ₽», 500 000 → «500 000,00 ₽».
 */
export function formatMoneyShort(
  value: number | null | undefined,
  options: MoneyFormatOptions = {},
): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  const { withCurrency = true } = options
  const suffix = withCurrency ? `${THIN_SPACE}${CURRENCY_SYMBOL}` : ''
  const absolute = Math.abs(value)

  if (absolute >= 1_000_000_000) {
    return `${formatSignificant(value / 1_000_000_000)} млрд${suffix}`
  }
  if (absolute >= 1_000_000) {
    return `${formatSignificant(value / 1_000_000)} млн${suffix}`
  }
  return formatMoney(value, options)
}

/** До двух знаков, без хвостовых нулей: 1.2345 → «1,23», 3 → «3». */
function formatSignificant(value: number): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
    .format(value)
    .replace(ANY_SPACE, THIN_SPACE)
}

/** 24 → «24,0 %», null → «—». Знак процента не домножает значение (оно уже в процентах). */
export function formatPercent(value: number | null | undefined, fractionDigits = 1): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  return `${formatNumber(value, fractionDigits)}${THIN_SPACE}%`
}

/** Отклонение со знаком: 11.11 → «+11,1 %», -8 → «-8,0 %», null → «—». */
export function formatDelta(value: number | null | undefined, fractionDigits = 1): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, fractionDigits)}${THIN_SPACE}%`
}

/** Количество без дробной части: 1520 → «1 520». */
export function formatCount(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  return formatNumber(value, 0)
}

/** Количество с долями: 128.5 → «128,5» (единицы к отгрузке бывают дробными). */
export function formatQuantity(value: number | null | undefined, fractionDigits = 3): string {
  if (!isFiniteNumber(value)) {
    return MISSING
  }
  return new Intl.NumberFormat('ru-RU', {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  })
    .format(value)
    .replace(ANY_SPACE, THIN_SPACE)
}

/** Деньги — целые рубли без копеек: для подписей на графике. */
export function formatMoneyCompactAxis(value: number): string {
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000) {
    return `${formatSignificant(value / 1_000_000)} млн`
  }
  if (absolute >= 1_000) {
    return `${formatSignificant(value / 1_000)} тыс`
  }
  return formatNumber(value, 0)
}

const MONTHS_SHORT = [
  'янв',
  'фев',
  'мар',
  'апр',
  'май',
  'июн',
  'июл',
  'авг',
  'сен',
  'окт',
  'ноя',
  'дек',
]

const MONTHS_FULL = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
]

interface ParsedMonth {
  year: number
  month: number
}

function parseMonth(month: string | null | undefined): ParsedMonth | null {
  const match = /^(\d{4})-(\d{2})/.exec(month ?? '')
  if (!match) {
    return null
  }
  const monthNumber = Number(match[2])
  if (monthNumber < 1 || monthNumber > 12) {
    return null
  }
  return { year: Number(match[1]), month: monthNumber }
}

/** «2026-10» → «окт 26» — подпись месяца на графике. */
export function formatMonthShort(month: string | null | undefined): string {
  const parsed = parseMonth(month)
  if (!parsed) {
    return MISSING
  }
  return `${MONTHS_SHORT[parsed.month - 1]} ${String(parsed.year).slice(2)}`
}

/** «2026-10» → «Октябрь 2026» — для всплывающей подсказки. */
export function formatMonthFull(month: string | null | undefined): string {
  const parsed = parseMonth(month)
  if (!parsed) {
    return MISSING
  }
  return `${MONTHS_FULL[parsed.month - 1]} ${parsed.year}`
}

/** «2026-10-11» → «11.10.2026». */
export function formatIsoDate(iso: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '')
  if (!match) {
    return MISSING
  }
  return `${match[3]}.${match[2]}.${match[1]}`
}

/** «2026-10-11T07:40:03» → «11.10.2026 07:40:03». */
export function formatIsoDateTime(iso: string | null | undefined): string {
  const date = formatIsoDate(iso)
  if (date === MISSING) {
    return MISSING
  }
  const time = /T(\d{2}:\d{2}(?::\d{2})?)/.exec(iso ?? '')
  return time ? `${date} ${time[1]}` : date
}

/** Возраст данных: 42 → «42 с», 300 → «5 мин», 7200 → «2 ч», 172800 → «2 дн». */
export function formatAge(seconds: number | null | undefined): string {
  if (!isFiniteNumber(seconds) || seconds < 0) {
    return MISSING
  }
  if (seconds < 60) {
    return `${Math.round(seconds)} с`
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} мин`
  }
  if (seconds < 86_400) {
    return `${Math.round(seconds / 3600)} ч`
  }
  return `${Math.round(seconds / 86_400)} дн`
}

/** Диапазон дат периода: «01.10.2026 — 11.10.2026». */
export function formatDateRange(
  from: string | null | undefined,
  to: string | null | undefined,
): string {
  const start = formatIsoDate(from)
  const end = formatIsoDate(to)
  if (start === MISSING && end === MISSING) {
    return MISSING
  }
  return `${start} — ${end}`
}

export function isNegative(value: number | null | undefined): boolean {
  return isFiniteNumber(value) && value < 0
}

/** Сегодняшняя дата в формате контракта (YYYY-MM-DD) — по локальному времени браузера. */
export function todayIso(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

/**
 * Тот же набор функций, но с настройками по умолчанию — удобно в шаблонах,
 * где одна и та же карточка форматирует несколько значений.
 */
export function useMoneyFormat(defaults: MoneyFormatOptions = {}) {
  return {
    formatMoney: (value: number | null | undefined, options: MoneyFormatOptions = {}) =>
      formatMoney(value, { ...defaults, ...options }),
    formatMoneyShort: (value: number | null | undefined, options: MoneyFormatOptions = {}) =>
      formatMoneyShort(value, { ...defaults, ...options }),
    formatPercent,
    formatDelta,
    formatCount,
    formatQuantity,
    formatAge,
    formatIsoDate,
    formatIsoDateTime,
    formatDateRange,
    isNegative,
  }
}
