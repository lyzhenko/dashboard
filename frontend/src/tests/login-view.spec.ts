import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { AntComponents } from '@/app/plugins'
import { getAccessToken, setAccessToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div>dashboard</div>' } },
      { path: '/login', name: 'login', component: LoginView },
      { path: '/:pathMatch(.*)*', component: { template: '<div>page</div>' } },
    ],
  })
}

async function mountLogin(redirect?: string): Promise<{ wrapper: VueWrapper; router: Router }> {
  const router = createTestRouter()
  await router.push(redirect ? { path: '/login', query: { redirect } } : '/login')
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: { plugins: [createPinia(), router, AntComponents] },
  })
  await flushPromises()
  return { wrapper, router }
}

async function fill(wrapper: VueWrapper, username: string, password: string): Promise<void> {
  await wrapper.get('input[autocomplete="username"]').setValue(username)
  await wrapper.get('input[autocomplete="current-password"]').setValue(password)
  await flushPromises()
}

describe('LoginView — экран входа', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setAccessToken(null)
    window.localStorage.clear()
    window.sessionStorage.clear()
  })

  it('кнопка входа отправляет форму (type=submit)', async () => {
    const { wrapper } = await mountLogin()
    const button = wrapper.get('[data-testid="login-submit"]')

    expect(button.attributes('type')).toBe('submit')
    expect(button.text()).toContain('Войти')
  })

  it('успешный вход держит токен в памяти и уводит на дашборд', async () => {
    const { wrapper, router } = await mountLogin()
    await fill(wrapper, 'rukovoditel', 'secret')

    // jsdom не отправляет форму по клику на кнопку — отправляем событие формы
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.accessToken).toBe('test-access-token')
    expect(auth.user?.fullName).toBe('Иванов И. И.')
    expect(getAccessToken()).toBe('test-access-token')
    expect(router.currentRoute.value.name).toBe('dashboard')

    // правило стека: токенов в localStorage/sessionStorage быть не должно
    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)
    expect(JSON.stringify(window.localStorage)).not.toContain('test-access-token')
  })

  it('после входа возвращает на исходный маршрут из ?redirect=', async () => {
    const { wrapper, router } = await mountLogin('/debtors')
    await fill(wrapper, 'rukovoditel', 'secret')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/debtors')
  })

  it('неверный пароль показывает ошибку и не пускает дальше', async () => {
    const { wrapper, router } = await mountLogin()
    await fill(wrapper, 'rukovoditel', 'wrong')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const error = wrapper.get('[data-testid="login-error"]')
    expect(error.text()).toContain('Неверный пользователь или пароль')
    expect(useAuthStore().isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('пустые поля не отправляются на сервер', async () => {
    const { wrapper } = await mountLogin()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[data-testid="login-error"]').text()).toContain(
      'Укажите пользователя и пароль',
    )
    expect(getAccessToken()).toBeNull()
  })
})
