<script setup lang="ts">
import { computed } from 'vue'

import { useMoneyFormat, type MoneyFormatOptions } from '@/composables/useMoneyFormat'

const props = withDefaults(
  defineProps<{
    value: number | null | undefined
    /** short — компактная запись крупных сумм: «1,23 млн ₽». */
    mode?: 'full' | 'short'
    withCurrency?: boolean
    fractionDigits?: number
    /** Красить отрицательные значения своим цветом (по умолчанию да). */
    colorNegative?: boolean
    /** Крупная цифра Roboto Slab — для карточек KPI. */
    strong?: boolean
    size?: 'small' | 'default' | 'large' | 'xlarge'
  }>(),
  {
    mode: 'full',
    withCurrency: true,
    fractionDigits: 2,
    colorNegative: true,
    strong: false,
    size: 'default',
  },
)

const money = useMoneyFormat()

const text = computed(() => {
  const options: MoneyFormatOptions = {
    withCurrency: props.withCurrency,
    fractionDigits: props.fractionDigits,
  }
  return props.mode === 'short'
    ? money.formatMoneyShort(props.value, options)
    : money.formatMoney(props.value, options)
})

const negative = computed(() => props.colorNegative && money.isNegative(props.value))
</script>

<template>
  <span
    class="money"
    :class="[
      `money--${size}`,
      {
        'money--negative': negative,
        'money--strong': strong,
        'money--muted': value === null || value === undefined,
      },
    ]"
    >{{ text }}</span
  >
</template>

<style scoped>
.money {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.money--strong {
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-weight: 600;
}

.money--small {
  font-size: 13px;
}

.money--large {
  font-size: 22px;
}

.money--xlarge {
  font-size: 30px;
  line-height: 1.15;
}

.money--negative {
  color: #a8071a;
}

.money--muted {
  color: #8c8c8c;
}
</style>
