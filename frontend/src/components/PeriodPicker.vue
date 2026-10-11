<script setup lang="ts">
import type { PeriodKind } from '@/api/dashboard'
import { PERIOD_OPTIONS } from '@/composables/useDashboard'

/** День / неделя / месяц / квартал / год — подписи по-русски. */
const model = defineModel<PeriodKind>({ required: true })
</script>

<template>
  <a-radio-group
    v-model:value="model"
    class="period-picker"
    button-style="solid"
    data-testid="period-picker"
  >
    <a-radio-button v-for="option in PERIOD_OPTIONS" :key="option.value" :value="option.value">
      {{ option.label }}
    </a-radio-button>
  </a-radio-group>
</template>

<style scoped>
.period-picker {
  white-space: nowrap;
}
</style>
