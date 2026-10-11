<script setup lang="ts">
import type { TopCounterparty } from '@/api/dashboard'
import { formatCount, formatMoney } from '@/composables/useMoneyFormat'

withDefaults(
  defineProps<{
    items: TopCounterparty[] | null | undefined
    loading?: boolean
    emptyText?: string
    /** Строки открывают детализацию (a-drawer) — подсказываем это словами. */
    clickable?: boolean
  }>(),
  {
    loading: false,
    emptyText: 'Данных за период нет',
    clickable: true,
  },
)

const emit = defineEmits<{ select: [item: TopCounterparty] }>()
</script>

<template>
  <div class="top-list" data-testid="top-list">
    <a-skeleton v-if="loading" active :paragraph="{ rows: 4 }" />
    <p v-else-if="!items || items.length === 0" class="top-list__empty">{{ emptyText }}</p>
    <template v-else>
      <ul class="top-list__items">
        <li v-for="(item, index) in items" :key="`${item.name}-${index}`" class="top-list__item">
          <component
            :is="clickable ? 'button' : 'div'"
            :type="clickable ? 'button' : undefined"
            class="top-list__row"
            @click="clickable && emit('select', item)"
          >
            <span class="top-list__rank">{{ index + 1 }}</span>
            <span class="top-list__main">
              <span class="top-list__name" :title="item.name">{{
                item.name || 'Без наименования'
              }}</span>
              <span class="top-list__meta">
                <template v-if="item.overdue > 0">
                  <span class="top-list__overdue">
                    просрочено {{ formatMoney(item.overdue) }} ·
                    {{ formatCount(item.maxOverdueDays) }} дн.
                  </span>
                </template>
                <template v-else>без просрочки</template>
              </span>
            </span>
            <span class="top-list__amount">{{ formatMoney(item.amount) }}</span>
          </component>
        </li>
      </ul>
      <p v-if="clickable" class="top-list__hint">Нажмите на строку, чтобы открыть детализацию</p>
    </template>
  </div>
</template>

<style scoped>
.top-list__items {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
}

.top-list__item + .top-list__item {
  border-top: 1px solid #f0f2f5;
}

.top-list__row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 6px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
}

button.top-list__row:hover {
  background: #f5f8fb;
}

.top-list__rank {
  flex: 0 0 18px;
  color: #8c8c8c;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.top-list__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1 1 auto;
}

.top-list__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-list__meta {
  font-size: 12px;
  color: #8c8c8c;
}

.top-list__overdue {
  color: #a8071a;
}

.top-list__amount {
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.top-list__empty {
  margin: 0;
  padding: 12px 0;
  color: #8c8c8c;
}

.top-list__hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
