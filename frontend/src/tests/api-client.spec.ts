import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  apiFetch,
  buildQuery,
  getAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from '@/api/client'
import { fetchOrganizations } from '@/api/dashboard'
import { API, server, testOrganizations } from './handlers'

describe('client — сборка запроса', () => {
  it('выбрасывает незаданные параметры', () => {
    expect(buildQuery({ date: '2026-10-11', period: 'month', organization: null })).toBe(
      '?date=2026-10-11&period=month',
    )
    expect(buildQuery({ organization: undefined, date: '' })).toBe('')
    expect(buildQuery()).toBe('')
  })
})

describe('client — перехват 401', () => {
  afterEach(() => {
    setAccessToken(null)
    setUnauthorizedHandler(null)
  })

  it('обновляет сессию по cookie и повторяет исходный запрос', async () => {
    let summaryAttempts = 0

    server.use(
      http.get(`${API}/dashboard/organizations`, ({ request }) => {
        summaryAttempts += 1
        if (request.headers.get('authorization') === 'Bearer refreshed-access-token') {
          return HttpResponse.json({ items: testOrganizations })
        }
        return HttpResponse.json(
          { detail: { code: 'unauthorized', message: 'Токен истёк' } },
          { status: 401 },
        )
      }),
    )

    setAccessToken('expired-token')
    const items = await fetchOrganizations()

    expect(items).toHaveLength(2)
    expect(items[0].name).toBe('ООО «Ромашка»')
    expect(summaryAttempts).toBe(2)
    expect(getAccessToken()).toBe('refreshed-access-token')
  })

  it('если refresh не удался — сообщает о выходе и бросает ApiError 401', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)

    server.use(
      http.get(`${API}/dashboard/organizations`, () =>
        HttpResponse.json(
          { detail: { code: 'unauthorized', message: 'Токен истёк' } },
          { status: 401 },
        ),
      ),
      http.post(`${API}/auth/refresh`, () =>
        HttpResponse.json(
          { detail: { code: 'unauthorized', message: 'Refresh-cookie нет' } },
          { status: 401 },
        ),
      ),
    )

    setAccessToken('expired-token')

    await expect(fetchOrganizations()).rejects.toBeInstanceOf(ApiError)
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(getAccessToken()).toBeNull()
  })

  it('ошибка 503 приходит с кодом контракта и текстом бэкенда', async () => {
    server.use(
      http.get(`${API}/dashboard/organizations`, () =>
        HttpResponse.json(
          { detail: { code: 'kpi_unavailable', message: 'Данные 1С недоступны: таймаут' } },
          { status: 503 },
        ),
      ),
    )

    await expect(fetchOrganizations()).rejects.toMatchObject({
      status: 503,
      code: 'kpi_unavailable',
      message: 'Данные 1С недоступны: таймаут',
    })
  })

  it('не-JSON ошибка не роняет разбор', async () => {
    server.use(
      http.get(
        `${API}/dashboard/organizations`,
        () => new HttpResponse('Bad gateway', { status: 502 }),
      ),
    )

    await expect(fetchOrganizations()).rejects.toMatchObject({
      status: 502,
      code: 'unknown',
    })
  })

  it('пустой ответ 204 не считается ошибкой', async () => {
    server.use(http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })))

    await expect(
      apiFetch<void>('/auth/logout', { method: 'POST', skipAuthRetry: true }),
    ).resolves.toBeUndefined()
  })
})
