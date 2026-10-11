import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { DashboardSummary, DebtorsResponse, DynamicsItem, Organization } from '@/api/dashboard'
import type { UserInfo } from '@/api/auth'

/** jsdom в тестах поднимается на этом origin (см. vite.config.ts, test.environmentOptions). */
export const API_ORIGIN = 'http://localhost:3000'
export const API = `${API_ORIGIN}/api/v1`

export const TEST_LOGIN = 'rukovoditel'
export const TEST_PASSWORD = 'secret'
export const TEST_ACCESS_TOKEN = 'test-access-token'
export const REFRESHED_ACCESS_TOKEN = 'refreshed-access-token'

export const testUser: UserInfo = {
  id: 1,
  username: TEST_LOGIN,
  fullName: 'Иванов И. И.',
  roles: ['viewer'],
}

export const testOrganizations: Organization[] = [
  {
    id: '0a1b2c3d-1111-2222-3333-444455556666',
    name: 'ООО «Ромашка»',
    inn: '7701234567',
    isDefault: false,
  },
  {
    id: '0a1b2c3d-1111-2222-3333-444455556667',
    name: 'ООО «Василёк»',
    inn: '7701234568',
    isDefault: false,
  },
]

/** Сводка по контракту: свежая, со всеми блоками. */
export const sampleSummary: DashboardSummary = {
  meta: {
    source: '1c',
    fetchedAt: '2026-10-11T07:40:03',
    ageSeconds: 42,
    stale: false,
    cached: true,
  },
  generatedAt: '2026-10-11T07:40:00',
  asOf: '2026-10-11',
  period: {
    kind: 'month',
    from: '2026-10-01',
    to: '2026-10-11',
    prevFrom: '2026-09-01',
    prevTo: '2026-09-11',
  },
  organization: null,
  money: { total: 1234567.89, accounts: 1000000.0, cash: 234567.89, currency: 'RUB' },
  sales: {
    revenue: 500000.0,
    revenuePrev: 450000.0,
    revenueDeltaPct: 11.11,
    revenueNet: 416666.67,
    grossProfit: 120000.0,
    grossProfitPrev: 90000.0,
    marginPct: 24.0,
    documents: 42,
    avgTicket: 11904.76,
  },
  receivables: {
    total: 800000.0,
    overdue: 150000.0,
    overduePct: 18.75,
    buckets: [
      { label: '0–7 дней', amount: 650000.0 },
      { label: '8–14 дней', amount: 50000.0 },
      { label: '15–30 дней', amount: 60000.0 },
      { label: '31–60 дней', amount: 30000.0 },
      { label: 'Свыше 60 дней', amount: 10000.0 },
    ],
  },
  payables: {
    total: 500000.0,
    overdue: 70000.0,
    overduePct: 14.0,
    buckets: [
      { label: '0–7 дней', amount: 300000.0 },
      { label: '8–14 дней', amount: 100000.0 },
      { label: '15–30 дней', amount: 50000.0 },
      { label: '31–60 дней', amount: 40000.0 },
      { label: 'Свыше 60 дней', amount: 10000.0 },
    ],
  },
  stock: { total: 3000000.0, skuCount: 1520, negativeCount: 0 },
  orders: {
    portfolio: 900000.0,
    count: 37,
    positions: 128.5,
    overdueCount: 4,
    overdueAmount: 120000.0,
    dueThisWeek: 250000.0,
    orderedAmount: 900000.0,
    paidAmount: 600000.0,
  },
  topDebtors: [{ name: 'ООО «Василёк»', amount: 300000.0, overdue: 100000.0, maxOverdueDays: 45 }],
  topSuppliers: [{ name: 'ООО «Поставщик»', amount: 200000.0, overdue: 0, maxOverdueDays: 0 }],
}

/** Устаревшая сводка: KPI_CACHE_TTL_SECONDS истёк, плашка «данные устарели» обязана появиться. */
export const staleSummary: DashboardSummary = {
  ...sampleSummary,
  meta: {
    source: '1c',
    fetchedAt: '2026-10-11T06:00:00',
    ageSeconds: 6003,
    stale: true,
    cached: true,
  },
}

/** Пустая база: нули и пустые массивы, ни одного null (кроме organization). */
export const emptySummary: DashboardSummary = {
  ...sampleSummary,
  meta: {
    source: '1c',
    fetchedAt: '2026-10-11T07:40:03',
    ageSeconds: 3,
    stale: false,
    cached: false,
  },
  money: { total: 0, accounts: 0, cash: 0, currency: 'RUB' },
  sales: {
    revenue: 0,
    revenuePrev: 0,
    revenueDeltaPct: 0,
    revenueNet: 0,
    grossProfit: 0,
    grossProfitPrev: 0,
    marginPct: 0,
    documents: 0,
    avgTicket: 0,
  },
  receivables: { total: 0, overdue: 0, overduePct: 0, buckets: [] },
  payables: { total: 0, overdue: 0, overduePct: 0, buckets: [] },
  stock: { total: 0, skuCount: 0, negativeCount: 0 },
  orders: {
    portfolio: 0,
    count: 0,
    positions: 0,
    overdueCount: 0,
    overdueAmount: 0,
    dueThisWeek: 0,
    orderedAmount: 0,
    paidAmount: 0,
  },
  topDebtors: [],
  topSuppliers: [],
}

export const sampleDynamics: DynamicsItem[] = Array.from({ length: 12 }, (_, index) => {
  const monthNumber = index + 11
  const year = monthNumber > 12 ? 2026 : 2025
  const month = monthNumber > 12 ? monthNumber - 12 : monthNumber
  const revenue = 400000 + index * 10000
  return {
    month: `${year}-${String(month).padStart(2, '0')}`,
    revenue,
    grossProfit: Math.round(revenue * 0.23),
    marginPct: 23.5,
  }
})

export const sampleDebtors: DebtorsResponse = {
  kind: 'receivable',
  asOf: '2026-10-11',
  total: 800000.0,
  overdue: 150000.0,
  items: [
    {
      name: 'ООО «Василёк»',
      amount: 300000.0,
      overdue: 100000.0,
      maxOverdueDays: 45,
      buckets: [
        { label: '0–7 дней', amount: 200000.0 },
        { label: '31–60 дней', amount: 100000.0 },
      ],
    },
  ],
}

export const handlers = [
  http.post(`${API}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { username?: string; password?: string }
    if (body.username === TEST_LOGIN && body.password === TEST_PASSWORD) {
      return HttpResponse.json({
        accessToken: TEST_ACCESS_TOKEN,
        expiresIn: 900,
        user: testUser,
      })
    }
    return HttpResponse.json(
      { detail: { code: 'unauthorized', message: 'Неверный пользователь или пароль' } },
      { status: 401 },
    )
  }),

  http.post(`${API}/auth/refresh`, () =>
    HttpResponse.json({ accessToken: REFRESHED_ACCESS_TOKEN, expiresIn: 900 }),
  ),

  http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/auth/me`, () => HttpResponse.json(testUser)),

  http.get(`${API}/dashboard/summary`, () => HttpResponse.json(sampleSummary)),

  http.get(`${API}/dashboard/dynamics`, () => HttpResponse.json({ items: sampleDynamics })),

  http.get(`${API}/dashboard/debtors`, () => HttpResponse.json(sampleDebtors)),

  http.get(`${API}/dashboard/organizations`, () => HttpResponse.json({ items: testOrganizations })),

  http.post(`${API}/dashboard/refresh`, () => HttpResponse.json(sampleSummary)),

  http.get(`${API}/health`, () => HttpResponse.json({ status: 'ok', database: 'ok', oneC: 'ok' })),
]

/**
 * Мок-сервер для тестов: реальных сетевых вызовов нет (правило стека).
 * Поднимается и гасится в src/tests/setup.ts.
 */
export const server = setupServer(...handlers)
