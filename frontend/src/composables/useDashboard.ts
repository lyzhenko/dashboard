import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { ApiError } from '@/api/client'
import {
  fetchDebtors,
  fetchDynamics,
  fetchOrganizations,
  fetchSummary,
  refreshDashboard,
  type DashboardSummary,
  type DebtorsQuery,
  type DynamicsQuery,
  type SummaryQuery,
} from '@/api/dashboard'
import type { PeriodKind } from '@/api/dashboard'

/** Подписи периодов по-русски — период всегда виден пользователю. */
export const PERIOD_LABELS: Record<PeriodKind, string> = {
  day: 'День',
  week: 'Неделя',
  month: 'Месяц',
  quarter: 'Квартал',
  year: 'Год',
}

export const PERIOD_OPTIONS: { value: PeriodKind; label: string }[] = (
  Object.keys(PERIOD_LABELS) as PeriodKind[]
).map((value) => ({ value, label: PERIOD_LABELS[value] }))

export function periodLabel(kind: PeriodKind | null | undefined): string {
  return kind && kind in PERIOD_LABELS ? PERIOD_LABELS[kind] : 'Период'
}

/** Сколько месяцев показывает график динамики. */
export const DYNAMICS_MONTHS = 12

/** Ключи запросов включают параметры периода и организации — иначе кеш склеит разные срезы. */
export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: (query: SummaryQuery) =>
    [
      ...dashboardKeys.all,
      'summary',
      {
        date: query.date ?? null,
        period: query.period ?? null,
        organization: query.organization ?? null,
      },
    ] as const,
  dynamics: (query: DynamicsQuery) =>
    [
      ...dashboardKeys.all,
      'dynamics',
      {
        months: query.months ?? DYNAMICS_MONTHS,
        date: query.date ?? null,
        organization: query.organization ?? null,
      },
    ] as const,
  debtors: (query: DebtorsQuery) =>
    [
      ...dashboardKeys.all,
      'debtors',
      {
        kind: query.kind ?? 'receivable',
        limit: query.limit ?? 10,
        date: query.date ?? null,
        organization: query.organization ?? null,
      },
    ] as const,
  organizations: () => [...dashboardKeys.all, 'organizations'] as const,
}

/** 4xx повторять бессмысленно (нет прав, нет сессии, неверный запрос); 503 — одну попытку. */
function shouldRetry(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false
  }
  return failureCount < 1
}

export function useSummaryQuery(query: MaybeRefOrGetter<SummaryQuery>) {
  return useQuery({
    queryKey: computed(() => dashboardKeys.summary(toValue(query))),
    queryFn: () => fetchSummary(toValue(query)),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    retry: shouldRetry,
  })
}

export function useDynamicsQuery(query: MaybeRefOrGetter<DynamicsQuery>) {
  return useQuery({
    queryKey: computed(() => dashboardKeys.dynamics(toValue(query))),
    queryFn: () => fetchDynamics(toValue(query)),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    retry: shouldRetry,
  })
}

export function useDebtorsQuery(
  query: MaybeRefOrGetter<DebtorsQuery>,
  options: { enabled?: MaybeRefOrGetter<boolean> } = {},
) {
  return useQuery({
    queryKey: computed(() => dashboardKeys.debtors(toValue(query))),
    queryFn: () => fetchDebtors(toValue(query)),
    enabled: computed(() => (options.enabled === undefined ? true : toValue(options.enabled))),
    staleTime: 60_000,
    retry: shouldRetry,
  })
}

/** Список организаций меняется редко — держим его в кеше дольше. */
export function useOrganizationsQuery() {
  return useQuery({
    queryKey: dashboardKeys.organizations(),
    queryFn: fetchOrganizations,
    staleTime: 10 * 60_000,
    retry: shouldRetry,
  })
}

/**
 * Принудительное обновление (POST /dashboard/refresh): ответ сразу кладём в кеш сводки,
 * а зависимые блоки (динамика, должники) помечаем устаревшими.
 */
export function useRefreshDashboardMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (query: SummaryQuery) => refreshDashboard(query),
    onSuccess: (summary, query) => {
      queryClient.setQueryData(dashboardKeys.summary(query), summary)
      void queryClient.invalidateQueries({ queryKey: [...dashboardKeys.all, 'dynamics'] })
      void queryClient.invalidateQueries({ queryKey: [...dashboardKeys.all, 'debtors'] })
    },
  })
}

/**
 * Пустая база — не ошибка: все блоки приходят нулями.
 * Такой ответ показываем как «данных за период нет», а не как сбой.
 */
export function isEmptySummary(summary: DashboardSummary | undefined | null): boolean {
  if (!summary) {
    return false
  }
  return (
    summary.money.total === 0 &&
    summary.sales.revenue === 0 &&
    summary.receivables.total === 0 &&
    summary.payables.total === 0 &&
    summary.stock.total === 0 &&
    summary.orders.portfolio === 0 &&
    summary.topDebtors.length === 0 &&
    summary.topSuppliers.length === 0
  )
}
