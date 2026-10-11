<script setup lang="ts">
import { ConfigProvider } from 'ant-design-vue'
import ruRU from 'ant-design-vue/es/locale/ru_RU'

import { theme } from '@/app/theme'
</script>

<template>
  <ConfigProvider :locale="ruRU" :theme="theme">
    <router-view />
  </ConfigProvider>
</template>

<style>
html,
body,
#app {
  height: 100%;
}

body {
  margin: 0;
  font-family:
    'Inter',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    Helvetica,
    Arial,
    sans-serif;
  font-size: 14px;
  color: #1f1f1f;
  background: #f4f6f9;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Цифры показателей — Roboto Slab, табличные: колонки цифр не «пляшут» */
.dashboard-number {
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
