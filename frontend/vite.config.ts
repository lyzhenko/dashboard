import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// Один origin: в разработке фронтенд ходит на /api через прокси Vite, на стенде — через nginx.
// CORS не настраивается и не нужен.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // cookie refresh-токена ходят тем же путём /api, поэтому прокси сохраняет заголовки как есть
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // Ant Design Vue регистрируется целиком (в шаблонах — теги a-*), поэтому выносим
        // библиотеки в отдельные файлы: их кешируют отдельно от кода приложения.
        manualChunks(id: string) {
          const path = id.replace(/\\/g, '/')
          if (!path.includes('node_modules')) {
            return undefined
          }
          if (path.includes('ant-design-vue') || path.includes('@ant-design')) {
            return 'vendor-antd'
          }
          if (path.includes('@tanstack')) {
            return 'vendor-query'
          }
          if (
            path.includes('vue-router') ||
            path.includes('pinia') ||
            path.includes('/vue/') ||
            path.includes('@vue/')
          ) {
            return 'vendor-vue'
          }
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    environmentOptions: {
      // jsdom даёт location.origin, относительно которого клиент строит абсолютный URL
      jsdom: { url: 'http://localhost:3000/' },
    },
    setupFiles: ['src/tests/setup.ts'],
    include: ['src/**/*.spec.ts'],
    restoreMocks: true,
  },
})
