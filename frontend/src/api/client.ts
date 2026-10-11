import type { components } from './schema'

/** База внутреннего API бэкенда. Проксируется Vite (dev) и nginx (стенд) — один origin. */
export const API_BASE = '/api/v1'

/** Ошибка запроса к API: HTTP-статус + код из контракта (docs/API-КОНТРАКТ.md, раздел 2). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, message: string, code = 'unknown') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export type RefreshResponse = components['schemas']['RefreshResponse']

export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Тело запроса: сериализуется в JSON. */
  body?: unknown
  query?: QueryParams
  /**
   * Не пытаться обновить сессию при 401. Ставится для самих запросов авторизации,
   * иначе повторный вход и refresh зациклятся.
   */
  skipAuthRetry?: boolean
  signal?: AbortSignal
}

// Access-токен живёт ТОЛЬКО в памяти модуля (и в Pinia как зеркало для реактивности).
// В localStorage/sessionStorage токенов нет — правило стека.
let accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

type UnauthorizedListener = () => void

let onUnauthorized: UnauthorizedListener | null = null

/** Вызывается, когда сессию восстановить не удалось: приложение уходит на /login. */
export function setUnauthorizedHandler(listener: UnauthorizedListener | null): void {
  onUnauthorized = listener
}

/** Собирает query-строку, выбрасывая пустые значения (не задан — значит «по умолчанию»). */
export function buildQuery(params?: QueryParams): string {
  if (!params) {
    return ''
  }
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') {
      continue
    }
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

/**
 * Абсолютный URL запроса. В браузере путь и так относительный, но fetch в jsdom (тесты)
 * требует абсолютный URL — поэтому подставляем origin текущего окна.
 */
function requestUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path
  }
  const origin = typeof globalThis.location === 'undefined' ? '' : globalThis.location.origin
  return `${origin}${API_BASE}${path}`
}

async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers = new Headers({ Accept: 'application/json' })
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  return fetch(requestUrl(path) + buildQuery(options.query), {
    method: options.method ?? 'GET',
    headers,
    // refresh-токен лежит в httpOnly cookie, поэтому cookie обязаны уходить всегда
    credentials: 'include',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })
}

async function parseJson<T>(response: Response): Promise<T | undefined> {
  if (response.status === 204) {
    return undefined
  }
  const text = await response.text()
  if (!text) {
    return undefined
  }
  return JSON.parse(text) as T
}

const STATUS_MESSAGES: Record<number, string> = {
  400: 'Некорректный запрос',
  401: 'Сессия истекла — требуется повторный вход',
  403: 'Недостаточно прав для этого действия',
  404: 'Данные не найдены',
  422: 'Запрос не прошёл проверку',
  503: 'Данные 1С недоступны',
}

const STATUS_CODES: Record<number, string> = {
  400: 'bad_request',
  401: 'unauthorized',
  403: 'forbidden',
  404: 'not_found',
  422: 'validation_error',
  503: 'kpi_unavailable',
}

/** Превращает ответ с ошибкой в ApiError, разбирая {"detail": {"code", "message"}}. */
async function toApiError(response: Response): Promise<ApiError> {
  const fallbackMessage = STATUS_MESSAGES[response.status] ?? `Ошибка запроса (${response.status})`
  const fallbackCode = STATUS_CODES[response.status] ?? 'unknown'

  try {
    const body = (await response.json()) as { detail?: unknown }
    const detail = body?.detail
    if (typeof detail === 'string' && detail) {
      return new ApiError(response.status, detail, fallbackCode)
    }
    if (detail && typeof detail === 'object') {
      const { code, message } = detail as { code?: unknown; message?: unknown }
      return new ApiError(
        response.status,
        typeof message === 'string' && message ? message : fallbackMessage,
        typeof code === 'string' && code ? code : fallbackCode,
      )
    }
  } catch {
    // тело не JSON или уже прочитано — сообщение берём по статусу
  }

  return new ApiError(response.status, fallbackMessage, fallbackCode)
}

let refreshPromise: Promise<boolean> | null = null

async function performRefresh(): Promise<boolean> {
  try {
    const response = await send('/auth/refresh', { method: 'POST', skipAuthRetry: true })
    if (!response.ok) {
      setAccessToken(null)
      return false
    }
    const data = await parseJson<RefreshResponse>(response)
    if (!data?.accessToken) {
      setAccessToken(null)
      return false
    }
    setAccessToken(data.accessToken)
    return true
  } catch {
    setAccessToken(null)
    return false
  }
}

/**
 * Обновление access-токена по httpOnly cookie.
 * Параллельные вызовы разделяют один запрос — иначе на каждое 401 летел бы свой refresh.
 */
export function refreshSession(): Promise<boolean> {
  refreshPromise ??= performRefresh().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

/**
 * Запрос к API с разбором ошибок.
 * 401 → POST /auth/refresh → повтор исходного запроса; если refresh не удался — обработчик
 * выхода (переход на /login) и ApiError.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  if (response.status === 401 && !options.skipAuthRetry) {
    const refreshed = await refreshSession()
    if (!refreshed) {
      setAccessToken(null)
      onUnauthorized?.()
      throw new ApiError(401, 'Сессия истекла — требуется повторный вход', 'unauthorized')
    }
    response = await send(path, options)
  }

  if (!response.ok) {
    throw await toApiError(response)
  }

  return (await parseJson<T>(response)) as T
}
