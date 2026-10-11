import { apiFetch, refreshSession, setAccessToken } from './client'
import type { components } from './schema'

export type LoginRequest = components['schemas']['LoginRequest']
export type LoginResponse = components['schemas']['LoginResponse']
export type UserInfo = components['schemas']['UserInfo']

/**
 * Вход. Access-токен приходит в теле и остаётся только в памяти,
 * refresh-токен бэкенд кладёт в httpOnly cookie (её выставляет сам ответ).
 */
export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: payload,
    skipAuthRetry: true,
  })
  setAccessToken(response.accessToken)
  return response
}

/** Молчаливое восстановление сессии по httpOnly cookie (используется защитой маршрутов). */
export function refreshAccessToken(): Promise<boolean> {
  return refreshSession()
}

/** Выход: бэкенд очищает cookie. Даже при ошибке сети локальную сессию нужно сбросить. */
export async function logout(): Promise<void> {
  try {
    await apiFetch<void>('/auth/logout', { method: 'POST', skipAuthRetry: true })
  } finally {
    setAccessToken(null)
  }
}

/** Текущий пользователь — для шапки дашборда. */
export function fetchCurrentUser(): Promise<UserInfo> {
  return apiFetch<UserInfo>('/auth/me')
}
