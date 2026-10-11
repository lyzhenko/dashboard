<script setup lang="ts">
import { computed } from 'vue'

import type { DebtBucket } from '@/api/dashboard'
import { formatMoney, formatPercent } from '@/composables/useMoneyFormat'

const props = withDefaults(
  defineProps<{
    /** Разбивка задолженности по возрасту долга: 0–7, 8–14, 15–30, 31–60, свыше 60 дней. */
    buckets: DebtBucket[] | null | undefined
    /** Итог блока — для доли каждой корзины. */
    total?: number | null
    loading?: boolean
  }>(),
  {
    total: null,
    loading: false,
  },
)

interface BucketRow {
  key: string
  label: string
  amount: number
  /** Длина полосы относительно самой крупной корзины, %. */
  width: number
  /** Доля в общем итоге, %. */
  share: number | null
}

const rows = computed<BucketRow[]>(() => {
  const buckets = props.buckets ?? []
  const amounts = buckets.map((bucket) => (Number.isFinite(bucket.amount) ? bucket.amount : 0))
  const maxAmount = amounts.reduce((max, amount) => Math.max(max, amount), 0)
  const sum = props.total ?? amounts.reduce((acc, amount) => acc + amount, 0)

  return buckets.map((bucket, index) => ({
    key: `${bucket.label}-${index}`,
    label: bucket.label,
    amount: amounts[index],
    width: maxAmount > 0 ? Math.round((amounts[index] / maxAmount) * 100) : 0,
    share: sum > 0 ? (amounts[index] / sum) * 100 : null,
  }))
})

const isEmpty = computed(
  () => rows.value.length === 0 || rows.value.every((row) => row.amount === 0),
)
</script>

<template>
  <div class="buckets" data-testid="debt-buckets">
    <a-skeleton v-if="loading" active :paragraph="{ rows: 3 }" />
    <p v-else-if="isEmpty" class="buckets__empty">Задолженности нет</p>
    <ul v-else class="buckets__list">
      <li v-for="row in rows" :key="row.key" class="buckets__row">
        <span class="buckets__label" :title="row.label">{{ row.label }}</span>
        <span class="buckets__bar">
          <span class="buckets__fill" :style="{ width: `${row.width}%` }" :data-width="row.width" />
        </span>
        <span class="buckets__amount">{{ formatMoney(row.amount) }}</span>
        <span class="buckets__share">{{
          row.share === null ? '—' : formatPercent(row.share)
        }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.buckets__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.buckets__row {
  display: grid;
  grid-template-columns: 118px 1fr auto 62px;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.buckets__label {
  color: #595959;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.buckets__bar {
  display: block;
  height: 10px;
  border-radius: 5px;
  background: #f0f2f5;
  overflow: hidden;
}

.buckets__fill {
  display: block;
  height: 100%;
  border-radius: 5px;
  background: #2f6fa8;
  transition: width 0.2s ease;
}

.buckets__amount {
  font-variant-numeric: tabular-nums;
  text-align: right;
  white-space: nowrap;
}

.buckets__share {
  text-align: right;
  color: #8c8c8c;
  font-variant-numeric: tabular-nums;
}

.buckets__empty {
  margin: 0;
  color: #8c8c8c;
}
</style>
