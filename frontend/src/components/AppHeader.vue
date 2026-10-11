<script setup lang="ts">
import { computed } from 'vue'

import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const userLabel = computed(() => auth.displayName || 'Пользователь')
const rolesLabel = computed(() => auth.roles.join(', '))

async function onLogout(): Promise<void> {
  await auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <header class="app-header">
    <div class="app-header__brand">
      <span class="app-header__title">Дашборд руководителя</span>
      <span class="app-header__subtitle">УНФ 3.0 · данные 1С</span>
    </div>

    <div class="app-header__right">
      <slot name="right" />
      <span class="app-header__user" :title="rolesLabel ? `Роли: ${rolesLabel}` : undefined">
        {{ userLabel }}
      </span>
      <a-button type="text" data-testid="logout" @click="onLogout">Выйти</a-button>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 64px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e6ebf0;
}

.app-header__brand {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.app-header__title {
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-size: 18px;
  font-weight: 700;
  color: #1f4e79;
}

.app-header__subtitle {
  font-size: 12px;
  color: #8c8c8c;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__user {
  font-size: 13px;
  color: #595959;
  white-space: nowrap;
}
</style>
