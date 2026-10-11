<script setup lang="ts">
import { computed, ref } from 'vue'

import { ApiError } from '@/api/client'
import {
  type DashboardSummary,
  type DebtKind,
  type DebtorsQuery,
  type DynamicsQuery,
  type PeriodKind,
  type SummaryQuery,
} from '@/api/dashboard'
import AppHeader from '@/components/AppHeader.vue'
import BarChart from '@/components/BarChart.vue'
import DebtBuckets from '@/components/DebtBuckets.vue'
import DeltaBadge from '@/components/DeltaBadge.vue'
import KpiCard from '@/components/KpiCard.vue'
import LineChart from '@/components/LineChart.vue'
import MoneyText from '@/components/MoneyText.vue'
import OrganizationSelect from '@/components/OrganizationSelect.vue'
import PeriodPicker from '@/components/PeriodPicker.vue'
import StaleBanner from '@/components/StaleBanner.vue'
import TopList from '@/components/TopList.vue'
import {
  formatAge,
  formatCount,
  formatDateRange,
  formatIsoDate,
  formatIsoDateTime,
  formatMoney,
  formatMonthFull,
  formatMonthShort,
  formatPercent,
  formatQuantity,
  todayIso,
} from '@/composables/useMoneyFormat'
import {
  DYNAMICS_MONTHS,
  isEmptySummary,
  periodLabel,
  useDebtorsQuery,
  useDynamicsQuery,
  useOrganizationsQuery,
  useRefreshDashboardMutation,
  useSummaryQuery,
} from '@/composables/useDashboard'

const period = ref<PeriodKind>('month')
const date = ref<string>(todayIso())
/** null — все организации (значение по умолчанию, контракт 1.2). */
const organization = ref<string | null>(null)

const summaryInput = computed<SummaryQuery>(() => ({
  date: date.value,
  period: period.value,
  organization: organization.value,
}))

const summary = useSummaryQuery(summaryInput)
const organizationsQuery = useOrganizationsQuery()
const refreshMutation = useRefreshDashboardMutation()

const data = computed<DashboardSummary | undefined>(() => summary.data.value)
const meta = computed(() => data.value?.meta)
const organizations = computed(() => organizationsQuery.data.value ?? [])

const showSkeletons = computed(
  () => !data.value && (summary.isPending.value || summary.isFetching.value),
)
const isUnauthorized = computed(
  () => summary.error.value instanceof ApiError && summary.error.value.status === 401,
)
const showError = computed(
  () =>
    Boolean(summary.error.value) && !isUnauthorized.value && !data.value && !showSkeletons.value,
)
const errorTitle = computed(() => {
  const error = summary.error.value
  if (error instanceof ApiError && error.code === 'kpi_unavailable') {
    return 'Данные 1С недоступны'
  }
  return 'Не удалось получить показатели'
})
const errorMessage = computed(() => {
  const error = summary.error.value
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Сервер не ответил. Проверьте соединение и повторите запрос.'
})

const refreshError = computed(() => {
  const error = refreshMutation.error.value
  if (!error) {
    return ''
  }
  return error instanceof ApiError ? error.message : 'Не удалось обновить данные из 1С'
})

const showEmptyNotice = computed(() => !showSkeletons.value && isEmptySummary(data.value))

/** Период всегда виден пользователю: подпись + реальные границы из ответа. */
const periodCaption = computed(() => {
  const info = data.value?.period
  const label = periodLabel(info?.kind ?? period.value)
  if (!info) {
    return `${label} · ${formatIsoDate(date.value)}`
  }
  return `${label} · ${formatDateRange(info.from, info.to)}`
})

const previousPeriodCaption = computed(() => {
  const info = data.value?.period
  return info ? `Предыдущий: ${formatDateRange(info.prevFrom, info.prevTo)}` : ''
})

const organizationCaption = computed(() => data.value?.organization?.name ?? 'Все организации')

/**
 * Проценты по контракту равны нулю и тогда, когда базы сравнения нет.
 * Чтобы ноль не выглядел как рост, при нулевой базе отдаём компоненту null.
 */
function percentOrNull(value: number, base: number | null | undefined): number | null {
  return base === null || base === undefined || base === 0 ? null : value
}

const sales = computed(() => data.value?.sales)
const revenueDelta = computed(() =>
  sales.value ? percentOrNull(sales.value.revenueDeltaPct, sales.value.revenuePrev) : null,
)
/** Рост валовой прибыли к прошлому периоду; null, если прошлая прибыль нулевая. */
const grossProfitGrowthPct = computed(() => {
  const block = sales.value
  if (!block || block.grossProfitPrev === 0) {
    return null
  }
  return ((block.grossProfit - block.grossProfitPrev) / block.grossProfitPrev) * 100
})
const noComparisonBase = computed(() => (sales.value?.revenuePrev ?? 0) === 0)
const marginText = computed(() => {
  const block = sales.value
  if (!block || block.revenue <= 0) {
    return '—'
  }
  return formatPercent(block.marginPct)
})

const receivablesOverdueShare = computed(() => {
  const block = data.value?.receivables
  if (!block || block.total <= 0) {
    return '—'
  }
  return formatPercent(block.overduePct)
})

const payablesOverdueShare = computed(() => {
  const block = data.value?.payables
  if (!block || block.total <= 0) {
    return '—'
  }
  return formatPercent(block.overduePct)
})

const dynamicsInput = computed<DynamicsQuery>(() => ({
  months: DYNAMICS_MONTHS,
  date: date.value,
  organization: organization.value,
}))

const dynamics = useDynamicsQuery(dynamicsInput)
const dynamicsLoading = computed(() => !dynamics.data.value && dynamics.isPending.value)

const dynamicsItems = computed(() => dynamics.data.value?.items ?? [])

const revenueItems = computed(() =>
  dynamicsItems.value.map((item) => ({
    key: item.month,
    label: formatMonthShort(item.month),
    title: formatMonthFull(item.month),
    value: item.revenue,
    lines: [
      { label: 'Валовая прибыль', value: formatMoney(item.grossProfit) },
      {
        label: 'Рентабельность',
        value: item.revenue > 0 ? formatPercent(item.marginPct) : '—',
      },
    ],
  })),
)

/** Рентабельность уходит в LineChart: нулевая выручка месяца — разрыв линии. */
const marginValues = computed(() =>
  dynamicsItems.value.map((item) => (item.revenue > 0 ? item.marginPct : null)),
)

// --- Детализация задолженности в выдвижной панели -------------------------------------

const drawerOpen = ref(false)
const drawerKind = ref<DebtKind>('receivable')

const drawerTitle = computed(() =>
  drawerKind.value === 'receivable' ? 'Кто нам должен' : 'Кому должны мы',
)

const debtorsInput = computed<DebtorsQuery>(() => ({
  kind: drawerKind.value,
  limit: 20,
  date: date.value,
  organization: organization.value,
}))

const debtors = useDebtorsQuery(debtorsInput, { enabled: drawerOpen })
const debtorsItems = computed(() => debtors.data.value?.items ?? [])

function openDebtors(kind: DebtKind): void {
  drawerKind.value = kind
  drawerOpen.value = true
}

// --- Действия -------------------------------------------------------------------------

async function onRefresh(): Promise<void> {
  try {
    await refreshMutation.mutateAsync(summaryInput.value)
  } catch {
    // текст ошибки показывает refreshError
  }
}

function onRetry(): void {
  void summary.refetch()
}

function onDateChange(value: unknown): void {
  if (typeof value === 'string' && value !== '') {
    date.value = value
  }
}

function onClickDebtors(): void {
  openDebtors('receivable')
}

function onClickSuppliers(): void {
  openDebtors('payable')
}
</script>

<template>
  <div class="dashboard">
    <AppHeader />

    <main class="dashboard__body">
      <a-card class="toolbar-card" :bordered="false">
        <div class="toolbar">
          <div class="toolbar__field">
            <span class="toolbar__label">Организация</span>
            <OrganizationSelect
              v-model="organization"
              :items="organizations"
              :loading="organizationsQuery.isPending.value"
            />
          </div>

          <div class="toolbar__field">
            <span class="toolbar__label">Период</span>
            <PeriodPicker v-model="period" />
          </div>

          <div class="toolbar__field">
            <span class="toolbar__label">Дата</span>
            <a-date-picker
              :value="date"
              value-format="YYYY-MM-DD"
              :allow-clear="false"
              @change="onDateChange"
            />
          </div>

          <div class="toolbar__field">
            <span class="toolbar__label">&nbsp;</span>
            <a-button
              type="primary"
              data-testid="refresh"
              :loading="refreshMutation.isPending.value"
              @click="onRefresh"
            >
              Обновить
            </a-button>
          </div>

          <div class="toolbar__freshness" data-testid="freshness">
            <span class="toolbar__period">{{ periodCaption }}</span>
            <span class="toolbar__org">{{ organizationCaption }}</span>
            <span v-if="previousPeriodCaption" class="toolbar__hint">
              {{ previousPeriodCaption }}
            </span>
            <span class="toolbar__meta">
              <template v-if="meta">
                <a-tag :color="meta.stale ? 'orange' : 'green'">
                  {{ meta.stale ? 'данные устарели' : 'данные свежие' }}
                </a-tag>
                <span>
                  обновлено {{ formatIsoDateTime(meta.fetchedAt) }} ·
                  {{ formatAge(meta.ageSeconds) }} назад<template v-if="meta.cached">
                    · из кеша</template
                  >
                </span>
              </template>
              <template v-else>свежесть данных неизвестна</template>
            </span>
          </div>
        </div>
      </a-card>

      <StaleBanner
        class="dashboard__banner"
        :stale="Boolean(meta?.stale)"
        :fetched-at="meta?.fetchedAt"
        :age-seconds="meta?.ageSeconds"
        :loading="refreshMutation.isPending.value"
        @refresh="onRefresh"
      />

      <a-alert
        v-if="refreshError"
        class="dashboard__banner"
        type="error"
        show-icon
        :message="refreshError"
      />

      <a-alert
        v-if="showEmptyNotice"
        class="dashboard__banner"
        data-testid="empty-notice"
        type="info"
        show-icon
        message="Данных за период нет"
        description="На выбранную дату и период в базе нет операций — все показатели нулевые. Это нормальный режим, а не ошибка."
      />

      <a-result
        v-if="showError"
        class="dashboard__error"
        data-testid="error-block"
        status="warning"
        :title="errorTitle"
        :sub-title="errorMessage"
      >
        <template #extra>
          <a-button type="primary" @click="onRetry">Повторить</a-button>
        </template>
      </a-result>

      <template v-else>
        <a-row class="dashboard__row" :gutter="[16, 16]">
          <!-- 1. Деньги -->
          <a-col :xs="24" :md="12" :xl="8">
            <KpiCard
              title="Деньги"
              :loading="showSkeletons"
              hint="Остатки денежных средств на дату"
            >
              <MoneyText :value="data?.money.total" mode="short" strong size="xlarge" />
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label">На счетах</span>
                  <span class="detail__value">{{ formatMoney(data?.money.accounts) }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">В кассе</span>
                  <span class="detail__value">{{ formatMoney(data?.money.cash) }}</span>
                </div>
              </div>
              <template #footer>
                Остатки на {{ formatIsoDate(data?.asOf ?? date) }} · {{ organizationCaption }}
              </template>
            </KpiCard>
          </a-col>

          <!-- 2. Выручка за период -->
          <a-col :xs="24" :md="12" :xl="8">
            <KpiCard
              title="Выручка за период"
              :loading="showSkeletons"
              :hint="`С НДС, как считает УНФ. ${previousPeriodCaption}`"
            >
              <div class="value-row">
                <MoneyText :value="data?.sales.revenue" mode="short" strong size="xlarge" />
                <DeltaBadge :value="revenueDelta" />
              </div>
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label">Без НДС</span>
                  <span class="detail__value">{{ formatMoney(data?.sales.revenueNet) }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Документов</span>
                  <span class="detail__value">{{ formatCount(data?.sales.documents) }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Средний чек</span>
                  <span class="detail__value">{{ formatMoney(data?.sales.avgTicket) }}</span>
                </div>
              </div>
              <template #footer>
                Прошлый период: {{ formatMoney(data?.sales.revenuePrev)
                }}<template v-if="noComparisonBase"> — базы сравнения нет</template>
              </template>
            </KpiCard>
          </a-col>

          <!-- 3. Валовая прибыль -->
          <a-col :xs="24" :md="12" :xl="8">
            <KpiCard
              title="Валовая прибыль"
              :loading="showSkeletons"
              hint="Выручка минус себестоимость"
            >
              <div class="value-row">
                <MoneyText :value="data?.sales.grossProfit" mode="short" strong size="xlarge" />
                <DeltaBadge :value="grossProfitGrowthPct" />
              </div>
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label">Рентабельность</span>
                  <span class="detail__value detail__value--strong">{{ marginText }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Прибыль прошлого периода</span>
                  <span class="detail__value">{{ formatMoney(data?.sales.grossProfitPrev) }}</span>
                </div>
              </div>
              <template #footer>Рентабельность = прибыль / выручка с НДС</template>
            </KpiCard>
          </a-col>
        </a-row>

        <a-row class="dashboard__row" :gutter="[16, 16]">
          <!-- 4. Дебиторская задолженность -->
          <a-col :xs="24" :lg="12">
            <KpiCard
              title="Дебиторская задолженность"
              :loading="showSkeletons"
              hint="Нам должны. Просрочка — по сроку оплаты по договору"
            >
              <MoneyText :value="data?.receivables.total" mode="short" strong size="xlarge" />
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label detail__label--alert">Просроченная</span>
                  <span class="detail__value detail__value--alert">
                    {{ formatMoney(data?.receivables.overdue) }}
                  </span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Доля просрочки</span>
                  <span class="detail__value">{{ receivablesOverdueShare }}</span>
                </div>
              </div>
              <div class="buckets-wrap">
                <span class="buckets-wrap__title">По возрасту долга</span>
                <DebtBuckets
                  :buckets="data?.receivables.buckets"
                  :total="data?.receivables.total"
                  :loading="showSkeletons"
                />
              </div>
              <template #footer>
                <a-button type="link" size="small" @click="onClickDebtors">
                  Показать всех должников
                </a-button>
              </template>
            </KpiCard>
          </a-col>

          <!-- 5. Кредиторская задолженность -->
          <a-col :xs="24" :lg="12">
            <KpiCard
              title="Кредиторская задолженность"
              :loading="showSkeletons"
              hint="Мы должны поставщикам"
            >
              <MoneyText :value="data?.payables.total" mode="short" strong size="xlarge" />
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label detail__label--alert">Просроченная</span>
                  <span class="detail__value detail__value--alert">
                    {{ formatMoney(data?.payables.overdue) }}
                  </span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Доля просрочки</span>
                  <span class="detail__value">{{ payablesOverdueShare }}</span>
                </div>
              </div>
              <div class="buckets-wrap">
                <span class="buckets-wrap__title">По возрасту долга</span>
                <DebtBuckets
                  :buckets="data?.payables.buckets"
                  :total="data?.payables.total"
                  :loading="showSkeletons"
                />
              </div>
              <template #footer>
                <a-button type="link" size="small" @click="onClickSuppliers">
                  Показать всех поставщиков
                </a-button>
              </template>
            </KpiCard>
          </a-col>
        </a-row>

        <a-row class="dashboard__row" :gutter="[16, 16]">
          <!-- 6. Запасы -->
          <a-col :xs="24" :lg="12">
            <KpiCard
              title="Запасы"
              :loading="showSkeletons"
              :tone="(data?.stock.negativeCount ?? 0) > 0 ? 'danger' : 'default'"
              hint="Стоимость запасов на складах"
            >
              <MoneyText :value="data?.stock.total" mode="short" strong size="xlarge" />
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label">Номенклатур</span>
                  <span class="detail__value">{{ formatCount(data?.stock.skuCount) }}</span>
                </div>
              </div>
              <a-alert
                v-if="(data?.stock.negativeCount ?? 0) > 0"
                class="dashboard__banner"
                data-testid="negative-stock"
                type="warning"
                show-icon
                :message="`Отрицательные остатки: ${formatCount(data?.stock.negativeCount)} номенклатур`"
                description="Это признак ошибок в учёте — проверьте движения по складам."
              />
              <template #footer
                >Стоимость и количество на {{ formatIsoDate(data?.asOf ?? date) }}</template
              >
            </KpiCard>
          </a-col>

          <!-- 7. Портфель заказов -->
          <a-col :xs="24" :lg="12">
            <KpiCard
              title="Портфель заказов"
              :loading="showSkeletons"
              :tone="(data?.orders.overdueCount ?? 0) > 0 ? 'warning' : 'default'"
              hint="Сумма открытых (не отгруженных) заказов покупателей"
            >
              <MoneyText :value="data?.orders.portfolio" mode="short" strong size="xlarge" />
              <div class="detail">
                <div class="detail__row">
                  <span class="detail__label">Заказов</span>
                  <span class="detail__value">{{ formatCount(data?.orders.count) }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">Единиц к отгрузке</span>
                  <span class="detail__value">{{ formatQuantity(data?.orders.positions) }}</span>
                </div>
                <div class="detail__row">
                  <span class="detail__label detail__label--alert">Просрочено к отгрузке</span>
                  <span class="detail__value detail__value--alert">
                    {{ formatCount(data?.orders.overdueCount) }} на
                    {{ formatMoney(data?.orders.overdueAmount) }}
                  </span>
                </div>
                <div class="detail__row">
                  <span class="detail__label">К отгрузке на неделе</span>
                  <span class="detail__value">{{ formatMoney(data?.orders.dueThisWeek) }}</span>
                </div>
              </div>
              <template #footer>
                За период оформлено {{ formatMoney(data?.orders.orderedAmount) }}, оплачено
                {{ formatMoney(data?.orders.paidAmount) }}
              </template>
            </KpiCard>
          </a-col>
        </a-row>

        <!-- Динамика за 12 месяцев -->
        <a-card class="chart-card" :bordered="false" title="Динамика за 12 месяцев">
          <template #extra>
            <div class="legend">
              <span class="legend__item">
                <i class="legend__swatch legend__swatch--bar" />выручка, ₽ (столбцы)
              </span>
              <span class="legend__item">
                <i class="legend__swatch legend__swatch--line" />рентабельность, % (линия)
              </span>
            </div>
          </template>
          <BarChart
            :items="revenueItems"
            :loading="dynamicsLoading"
            :height="300"
            value-label="Выручка"
            aria-label="Выручка и рентабельность по месяцам"
            empty-text="Данных за период нет"
          >
            <template #overlay="{ width, height, plotTop, plotBottom, plotLeft, plotRight }">
              <LineChart
                :values="marginValues"
                :width="width"
                :height="height"
                :plot-top="plotTop"
                :plot-bottom="plotBottom"
                :plot-left="plotLeft"
                :plot-right="plotRight"
              />
            </template>
          </BarChart>
        </a-card>

        <!-- Топ-5 должников и поставщиков -->
        <a-row class="dashboard__row" :gutter="[16, 16]">
          <a-col :xs="24" :lg="12">
            <a-card class="list-card" :bordered="false" title="Топ-5 должников">
              <TopList
                :items="data?.topDebtors"
                :loading="showSkeletons"
                empty-text="Дебиторской задолженности нет"
                @select="openDebtors('receivable')"
              />
            </a-card>
          </a-col>
          <a-col :xs="24" :lg="12">
            <a-card class="list-card" :bordered="false" title="Топ-5 поставщиков">
              <TopList
                :items="data?.topSuppliers"
                :loading="showSkeletons"
                empty-text="Кредиторской задолженности нет"
                @select="openDebtors('payable')"
              />
            </a-card>
          </a-col>
        </a-row>
      </template>
    </main>

    <a-drawer
      v-model:open="drawerOpen"
      :title="drawerTitle"
      placement="right"
      :width="720"
      data-testid="debtors-drawer"
    >
      <a-spin :spinning="debtors.isPending.value">
        <a-alert
          v-if="debtors.error.value"
          class="dashboard__banner"
          type="error"
          show-icon
          message="Не удалось получить детализацию"
        >
          <template #description>
            <a-button size="small" @click="debtors.refetch()">Повторить</a-button>
          </template>
        </a-alert>

        <div class="drawer-summary">
          <span>
            Всего: <MoneyText :value="debtors.data.value?.total" with-currency strong />
          </span>
          <span>
            Просрочено:
            <MoneyText :value="debtors.data.value?.overdue" with-currency strong color-negative />
          </span>
          <span class="drawer-summary__date">
            на {{ formatIsoDate(debtors.data.value?.asOf ?? date) }}
          </span>
        </div>

        <p v-if="debtorsItems.length === 0" class="drawer-empty">Задолженности нет</p>

        <div v-for="item in debtorsItems" :key="item.name" class="drawer-item">
          <div class="drawer-item__head">
            <span class="drawer-item__name">{{ item.name }}</span>
            <MoneyText :value="item.amount" strong />
          </div>
          <div class="drawer-item__meta">
            <span v-if="item.overdue > 0" class="detail__value--alert">
              просрочено {{ formatMoney(item.overdue) }} ·
              {{ formatCount(item.maxOverdueDays) }} дн.
            </span>
            <span v-else>без просрочки</span>
          </div>
          <DebtBuckets :buckets="item.buckets" :total="item.amount" />
        </div>
      </a-spin>
    </a-drawer>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: #f4f6f9;
}

.dashboard__body {
  padding: 16px 24px 32px;
}

.toolbar-card {
  border-radius: 12px;
  border: 1px solid #e6ebf0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
}

.toolbar__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.toolbar__label {
  font-size: 12px;
  color: #8c8c8c;
}

.toolbar__freshness {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-left: auto;
  text-align: right;
  font-size: 12px;
  color: #595959;
}

.toolbar__period {
  font-family: 'Roboto Slab', 'Inter', Georgia, serif;
  font-size: 14px;
  font-weight: 600;
  color: #1f4e79;
}

.toolbar__org {
  font-size: 12px;
  color: #1f1f1f;
}

.toolbar__hint,
.toolbar__meta {
  font-size: 12px;
  color: #8c8c8c;
}

.toolbar__meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-end;
}

.dashboard__banner {
  margin-top: 12px;
}

.dashboard__row {
  margin-top: 16px;
}

.dashboard__error {
  margin-top: 24px;
  background: #fff;
  border-radius: 12px;
}

.value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.detail__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.detail__label {
  color: #595959;
}

.detail__label--alert {
  color: #a8071a;
}

.detail__value {
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.detail__value--strong {
  font-weight: 600;
}

.detail__value--alert {
  color: #a8071a;
  font-weight: 500;
}

.buckets-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.buckets-wrap__title {
  font-size: 12px;
  color: #8c8c8c;
}

.chart-card,
.list-card {
  margin-top: 16px;
  border-radius: 12px;
  border: 1px solid #e6ebf0;
}

.legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #595959;
}

.legend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend__swatch {
  display: inline-block;
  width: 14px;
  height: 8px;
  border-radius: 2px;
}

.legend__swatch--bar {
  background: #2f6fa8;
}

.legend__swatch--line {
  width: 18px;
  height: 3px;
  background: #d4770b;
}

.drawer-summary {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
  font-size: 13px;
}

.drawer-summary__date {
  color: #8c8c8c;
}

.drawer-empty {
  color: #8c8c8c;
}

.drawer-item {
  padding: 12px 0;
  border-bottom: 1px solid #f5f7fa;
}

.drawer-item__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.drawer-item__name {
  font-weight: 600;
}

.drawer-item__meta {
  margin: 4px 0 8px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
