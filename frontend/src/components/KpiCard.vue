<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    /** Подпись под заголовком: что именно показано. */
    caption?: string
    loading?: boolean
    /** Подсветка проблемного блока: отрицательные остатки, просрочка. */
    tone?: 'default' | 'warning' | 'danger'
    hint?: string
  }>(),
  {
    caption: '',
    loading: false,
    tone: 'default',
    hint: '',
  },
)
</script>

<template>
  <a-card class="kpi" :class="`kpi--${tone}`" :bordered="false">
    <template #title>
      <div class="kpi__head">
        <span class="kpi__title">{{ title }}</span>
        <a-tooltip v-if="hint" :title="hint">
          <span class="kpi__hint" aria-hidden="true">?</span>
        </a-tooltip>
      </div>
    </template>
    <div class="kpi__body">
      <a-skeleton v-if="loading" active :paragraph="{ rows: 3 }" />
      <template v-else>
        <slot />
      </template>
    </div>
    <div v-if="!loading && ($slots.footer || caption)" class="kpi__footer">
      <slot name="footer">
        <span class="kpi__caption">{{ caption }}</span>
      </slot>
    </div>
  </a-card>
</template>

<style scoped>
.kpi {
  height: 100%;
  border: 1px solid #e6ebf0;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgb(15 40 70 / 4%);
}

.kpi--warning {
  border-color: #ffe58f;
}

.kpi--danger {
  border-color: #ffccc7;
}

.kpi__head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.kpi__title {
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
}

.kpi__hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #f0f2f5;
  color: #8c8c8c;
  font-size: 11px;
  cursor: help;
}

.kpi__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 72px;
}

.kpi__footer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #f0f2f5;
  font-size: 12px;
  color: #595959;
}

.kpi__caption {
  display: block;
}
</style>
