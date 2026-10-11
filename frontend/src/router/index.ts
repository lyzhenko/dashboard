import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true, title: 'Дашборд руководителя' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: 'Вход — Дашборд руководителя' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'dashboard' },
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/**
 * Защита маршрутов.
 * Приватный маршрут без access-токена сначала пробует восстановить сессию по
 * httpOnly cookie (POST /auth/refresh) — иначе после F5 пользователя выбрасывало бы на вход.
 */
router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (to.name === 'login' && auth.isAuthenticated) {
      return { name: 'dashboard' }
    }
    return true
  }

  if (auth.isAuthenticated) {
    return true
  }

  const restored = await auth.ensureSession()
  if (restored) {
    return true
  }

  return {
    name: 'login',
    query: to.fullPath === '/' ? {} : { redirect: to.fullPath },
  }
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : 'Дашборд руководителя'
  document.title = title
})

export default router
