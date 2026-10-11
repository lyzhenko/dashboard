import { createApp } from 'vue'

// Шрифты self-hosted через @fontsource — внешних CDN в проекте нет
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/roboto-slab/500.css'
import '@fontsource/roboto-slab/700.css'
import 'ant-design-vue/dist/reset.css'
import 'dayjs/locale/ru'

import { setUnauthorizedHandler } from '@/api/client'
import App from '@/app/App.vue'
import { installPlugins } from '@/app/plugins'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)

installPlugins(app)
app.use(router)

// 401, который не удалось погасить refresh-токеном: сессия кончилась — уходим на вход.
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    void router.replace({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
