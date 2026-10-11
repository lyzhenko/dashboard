import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshAccessToken,
  type LoginRequest,
  type UserInfo,
} from '@/api/auth'
import { getAccessToken, setAccessToken } from '@/api/client'

/**
 * Состояние сессии.
 *
 * Access-токен живёт в памяти: источник истины — модульная переменная api/client,
 * здесь лежит её реактивное зеркало (чтобы шапка и защита маршрутов перерисовывались).
 * Refresh-токен — httpOnly cookie, фронтенд его не видит и не хранит.
 */
export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(getAccessToken())
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)
  /** Была ли уже попытка восстановить сессию — чтобы не спрашивать повторно на каждом переходе. */
  const sessionChecked = ref(false)

  const isAuthenticated = computed(() => Boolean(accessToken.value))
  const displayName = computed(() => user.value?.fullName || user.value?.username || '')
  const roles = computed(() => user.value?.roles ?? [])

  function applyToken(token: string | null): void {
    setAccessToken(token)
    accessToken.value = token
  }

  function clear(): void {
    applyToken(null)
    user.value = null
  }

  async function login(credentials: LoginRequest): Promise<UserInfo> {
    loading.value = true
    try {
      const response = await loginRequest(credentials)
      applyToken(response.accessToken)
      user.value = response.user
      sessionChecked.value = true
      return response.user
    } finally {
      loading.value = false
    }
  }

  async function loadUser(): Promise<UserInfo | null> {
    if (!accessToken.value) {
      return null
    }
    user.value = await fetchCurrentUser()
    return user.value
  }

  /**
   * Восстановление сессии после перезагрузки страницы: access-токена в памяти нет,
   * но refresh-токен в httpOnly cookie может быть жив.
   */
  async function ensureSession(): Promise<boolean> {
    if (isAuthenticated.value) {
      return true
    }
    const refreshed = await refreshAccessToken()
    sessionChecked.value = true
    if (!refreshed) {
      clear()
      return false
    }
    applyToken(getAccessToken())
    try {
      await loadUser()
    } catch {
      // данные пользователя не критичны: показать дашборд важнее, чем имя в шапке
    }
    return true
  }

  async function logout(): Promise<void> {
    loading.value = true
    try {
      await logoutRequest()
    } finally {
      clear()
      loading.value = false
    }
  }

  return {
    accessToken,
    user,
    loading,
    sessionChecked,
    isAuthenticated,
    displayName,
    roles,
    login,
    loadUser,
    ensureSession,
    logout,
    clear,
  }
})
