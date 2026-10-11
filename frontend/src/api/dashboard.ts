import { apiFetch } from './client'
import type { components } from './schema'

/**
 * Сгенерированные схемы и полная форма ответа.
 *
 * `openapi.json` описывает поля блоков необязательными: у моделей бэкенда есть
 * значения по умолчанию, чтобы частичный ответ 1С не превращался в ошибку
 * валидации (см. `backend/app/schemas/dashboard.py`). В самом ответе блоки есть
 * всегда — бэкенд заполняет отсутствующее нулями, и это покрыто тестами, — поэтому
 * в коде приложения используется полная форма: так экраны не обязаны проверять
 * каждый блок на `undefined`.
 *
 * Имена схем сопоставлены с доменными именами здесь же: после `pnpm api:types`
 * достаточно сверить таблицу ниже, экраны и компоненты перегенерация не задевает.
 */
type Schemas = components['schemas']

/** Убирает только `undefined` (необязательность), сохраняя смысловой `null`. */
type NoUndefined<T> = T extends undefined ? never : T

/**
 * Полная форма: все поля и элементы присутствуют; `null` сохраняется там, где он
 * смысловой (например, `organization: null` — сводка по всем организациям).
 */
type Complete<T> = T extends (infer U)[]
  ? Complete<U>[]
  : T extends object
    ? { [K in keyof T]-?: Complete<NoUndefined<T[K]>> }
    : NoUndefined<T>

export type DashboardSummary = Complete<Schemas['SummaryResponse']>
export type SummaryMeta = Complete<Schemas['KpiMeta']>
export type PeriodInfo = Complete<Schemas['PeriodBlock']>
export type MoneyBlock = Complete<Schemas['MoneyBlock']>
export type SalesBlock = Complete<Schemas['SalesBlock']>
export type ReceivablesBlock = Complete<Schemas['ReceivablesBlock']>
export type PayablesBlock = Complete<Schemas['PayablesBlock']>
export type StockBlock = Complete<Schemas['StockBlock']>
export type OrdersBlock = Complete<Schemas['OrdersBlock']>
export type DebtBucket = Complete<Schemas['Bucket']>
export type TopCounterparty = Complete<Schemas['Counterparty']>
export type Organization = Complete<Schemas['OrganizationItem']>
export type DynamicsItem = Complete<Schemas['DynamicsItem']>
export type DynamicsResponse = Complete<Schemas['DynamicsResponse']>
export type DebtorsItem = Complete<Schemas['DebtorItem']>
export type DebtorsResponse = Complete<Schemas['DebtorsResponse']>
export type OrganizationsResponse = Complete<Schemas['OrganizationsResponse']>
export type HealthResponse = Complete<Schemas['HealthResponse']>

// Строковые перечисления: openapi-typescript не экспортирует схемы по именам,
// поэтому объявляем их здесь — отсюда их и импортируют экраны.
export type PeriodKind = Schemas['PeriodKind']
export type DebtKind = Schemas['DebtorKind']

/** Параметры сводки: дата остатков, период оборота, организация (не задана — все). */
export interface SummaryQuery {
  date?: string
  period?: PeriodKind
  organization?: string | null
}

export interface DynamicsQuery {
  months?: number
  date?: string
  organization?: string | null
}

export interface DebtorsQuery {
  kind?: DebtKind
  limit?: number
  date?: string
  organization?: string | null
}

export function fetchSummary(query: SummaryQuery = {}): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/dashboard/summary', { query: { ...query } })
}

export function fetchDynamics(query: DynamicsQuery = {}): Promise<DynamicsResponse> {
  return apiFetch<DynamicsResponse>('/dashboard/dynamics', { query: { ...query } })
}

export function fetchDebtors(query: DebtorsQuery = {}): Promise<DebtorsResponse> {
  return apiFetch<DebtorsResponse>('/dashboard/debtors', { query: { ...query } })
}

export async function fetchOrganizations(): Promise<Organization[]> {
  const response = await apiFetch<OrganizationsResponse>('/dashboard/organizations')
  // Пустой список организаций — не ошибка: дашборд покажет сводку по всем.
  return response.items ?? []
}

/** Принудительное перечитывание данных из 1С: возвращает свежую сводку. */
export function refreshDashboard(query: SummaryQuery = {}): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/dashboard/refresh', { method: 'POST', query: { ...query } })
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health')
}
