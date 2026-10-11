<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const error = ref('')
const submitting = ref(false)

const canSubmit = computed(() => form.username.trim().length > 0 && form.password.length > 0)

const redirectTarget = computed(() =>
  typeof route.query.redirect === 'string' && route.query.redirect !== ''
    ? route.query.redirect
    : '/',
)

async function onSubmit(): Promise<void> {
  if (submitting.value) {
    return
  }
  error.value = ''

  if (!canSubmit.value) {
    error.value = 'Укажите пользователя и пароль'
    return
  }

  submitting.value = true
  try {
    await auth.login({ username: form.username.trim(), password: form.password })
    await router.replace(redirectTarget.value)
  } catch (cause) {
    if (cause instanceof ApiError) {
      error.value = cause.status === 401 ? 'Неверный пользователь или пароль' : cause.message
    } else {
      error.value = 'Сервер недоступен. Проверьте соединение и повторите вход.'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login">
    <a-card class="login__card" :bordered="false">
      <h1 class="login__title">Дашборд руководителя</h1>
      <p class="login__subtitle">УНФ 3.0 · вход в дашборд</p>

      <a-alert
        v-if="error"
        class="login__error"
        data-testid="login-error"
        type="error"
        show-icon
        :message="error"
      />

      <!-- submit вешаем на форму: jsdom не отправляет форму по клику на кнопку -->
      <form class="login__form" novalidate @submit.prevent="onSubmit">
        <label class="login__label" for="login-username">Пользователь</label>
        <a-input
          id="login-username"
          v-model:value="form.username"
          size="large"
          autocomplete="username"
          placeholder="rukovoditel"
          :disabled="submitting"
        />

        <label class="login__label" for="login-password">Пароль</label>
        <a-input-password
          id="login-password"
          v-model:value="form.password"
          size="large"
          autocomplete="current-password"
          :disabled="submitting"
        />

        <a-button
          class="login__submit"
          data-testid="login-submit"
          type="primary"
          size="large"
          block
          html-type="submit"
          :loading="submitting"
          :disabled="submitting"
        >
          Войти
        </a-button>
      </form>
    </a-card>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background: linear-gradient(180deg, #f4f6f9 0%, #e9eef5 100%);
}

.login__card {
  width: 100%;
  max-width: 400px;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgb(15 40 70 / 10%);
}

.login__title {
  margin: 0 0 4px;
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-size: 22px;
  color: #1f4e79;
}

.login__subtitle {
  margin: 0 0 20px;
  font-size: 13px;
  color: #8c8c8c;
}

.login__error {
  margin-bottom: 16px;
}

.login__form {
  display: flex;
  flex-direction: column;
}

.login__label {
  margin-bottom: 6px;
  font-size: 13px;
  color: #595959;
}

.login__form :deep(.ant-input-affix-wrapper),
.login__form :deep(.ant-input) {
  margin-bottom: 16px;
}

.login__submit {
  margin-top: 4px;
}
</style>
