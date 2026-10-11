<script setup lang="ts">
import { computed } from 'vue'

import { formatDelta } from '@/composables/useMoneyFormat'

const props = withDefaults(
  defineProps<{
    /** Отклонение в процентах (уже в процентах, не доля). null — базы сравнения нет. */
    value: number | null | undefined
    fractionDigits?: number
    /** Пояснение для нативной подсказки. */
    hint?: string
    /**
     * Ноль показывать прочерком: по контракту процент равен нулю и тогда, когда
     * базы сравнения нет, поэтому «0,0 %» нельзя выдавать за рост.
     */
    zeroAsDash?: boolean
  }>(),
  {
    fractionDigits: 1,
    hint: 'Отклонение от прошлого периода такой же длины',
    zeroAsDash: true,
  },
)

const hasValue = computed(
  () => props.value !== null && props.value !== undefined && Number.isFinite(props.value),
)

const isZero = computed(() => hasValue.value && props.value === 0)

const direction = computed(() => {
  if (!hasValue.value || (isZero.value && props.zeroAsDash)) {
    return 'unknown'
  }
  if (props.value! > 0) {
    return 'up'
  }
  if (props.value! < 0) {
    return 'down'
  }
  return 'flat'
})

const icon = computed(() => {
  if (direction.value === 'up') {
    return '▲'
  }
  if (direction.value === 'down') {
    return '▼'
  }
  return ''
})

const text = computed(() =>
  !hasValue.value || (isZero.value && props.zeroAsDash)
    ? '—'
    : formatDelta(props.value, props.fractionDigits),
)

const label = computed(() => {
  if (!hasValue.value) {
    return 'Нет базы сравнения: прошлый период пуст'
  }
  if (isZero.value && props.zeroAsDash) {
    return 'Изменений нет'
  }
  return props.hint
})
</script>

<template>
  <span class="delta" :class="`delta--${direction}`" :title="label" data-testid="delta-badge">
    <span v-if="icon" class="delta__icon" aria-hidden="true">{{ icon }}</span>
    <span class="delta__value">{{ text }}</span>
  </span>
</template>

<style scoped>
.delta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.delta--up {
  color: #237804;
}

.delta--down {
  color: #a8071a;
}

.delta--flat,
.delta--unknown {
  color: #8c8c8c;
}

.delta__icon {
  font-size: 11px;
  line-height: 1;
}
</style>
