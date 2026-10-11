<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { formatMoney, formatMoneyCompactAxis } from '@/composables/useMoneyFormat'

/** Столбец диаграммы: подпись по оси X и значение. */
interface BarChartItem {
  key: string
  label: string
  value: number
  /** Заголовок подсказки; по умолчанию — label. */
  title?: string
  /** Дополнительные строки подсказки, например рентабельность месяца. */
  lines?: { label: string; value: string }[]
}

const props = withDefaults(
  defineProps<{
    items: BarChartItem[]
    height?: number
    loading?: boolean
    emptyText?: string
    /** Как показать значение в подсказке (по умолчанию — деньги с копейками). */
    valueFormatter?: (value: number) => string
    /** Подпись строки значения в подсказке. */
    valueLabel?: string
    ariaLabel?: string
  }>(),
  {
    height: 280,
    loading: false,
    emptyText: 'Данных за период нет',
    valueFormatter: (value: number) => formatMoney(value),
    valueLabel: 'Значение',
    ariaLabel: 'Диаграмма по месяцам',
  },
)

/** Геометрия графика в пикселях: ширина измеряется по контейнеру, высота — из props. */
const PAD_LEFT = 84
const PAD_RIGHT = 20
const PAD_TOP = 20
const PAD_BOTTOM = 44
const GRID_STEPS = 4
const BAR_MAX_WIDTH = 54
const MIN_WIDTH = 320

const container = ref<HTMLElement | null>(null)
const width = ref(720)

let resizeObserver: ResizeObserver | null = null

function measure(element: HTMLElement): void {
  const measured = element.clientWidth
  if (measured > 0) {
    width.value = Math.max(MIN_WIDTH, Math.round(measured))
  }
}

onMounted(() => {
  const element = container.value
  if (!element) {
    return
  }
  measure(element)
  if (typeof ResizeObserver === 'undefined') {
    return
  }
  resizeObserver = new ResizeObserver((entries) => {
    const measured = entries[0]?.contentRect.width ?? 0
    if (measured > 0) {
      width.value = Math.max(MIN_WIDTH, Math.round(measured))
    }
  })
  resizeObserver.observe(element)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

const plotHeight = computed(() => Math.max(1, props.height - PAD_TOP - PAD_BOTTOM))
const plotWidth = computed(() => Math.max(1, width.value - PAD_LEFT - PAD_RIGHT))
const scaleMax = computed(() => {
  const max = props.items.reduce((acc, item) => Math.max(acc, item.value), 0)
  return max > 0 ? max : 1
})
const bandWidth = computed(() => plotWidth.value / Math.max(1, props.items.length))
const barWidth = computed(() => Math.min(BAR_MAX_WIDTH, Math.max(6, bandWidth.value * 0.56)))

const bars = computed(() =>
  props.items.map((item, index) => {
    const value = Number.isFinite(item.value) ? item.value : 0
    const barHeight = (Math.max(0, value) / scaleMax.value) * plotHeight.value
    return {
      key: item.key,
      index,
      item,
      value,
      x: PAD_LEFT + bandWidth.value * index + (bandWidth.value - barWidth.value) / 2,
      y: PAD_TOP + plotHeight.value - barHeight,
      width: barWidth.value,
      height: barHeight,
      centerX: PAD_LEFT + bandWidth.value * (index + 0.5),
    }
  }),
)

/** Линии сетки и подписи значений по оси Y. */
const gridLines = computed(() =>
  Array.from({ length: GRID_STEPS + 1 }, (_, step) => ({
    value: (scaleMax.value * step) / GRID_STEPS,
    y: PAD_TOP + plotHeight.value * (1 - step / GRID_STEPS),
  })),
)

/** Границы области построения — их получает линия рентабельности через слот overlay. */
const plot = computed(() => ({
  plotTop: PAD_TOP,
  plotBottom: PAD_BOTTOM,
  plotLeft: PAD_LEFT,
  plotRight: PAD_RIGHT,
}))

function bandStyle(index: number): Record<string, string> {
  return {
    left: `${PAD_LEFT + bandWidth.value * index}px`,
    width: `${bandWidth.value}px`,
    top: `${PAD_TOP}px`,
    bottom: `${PAD_BOTTOM}px`,
  }
}
</script>

<template>
  <div ref="container" class="chart" data-testid="bar-chart">
    <a-skeleton v-if="loading" active :paragraph="{ rows: 6 }" />
    <p v-else-if="items.length === 0" class="chart__empty">{{ emptyText }}</p>
    <div v-else class="chart__stack" :style="{ height: `${height}px` }">
      <svg
        class="chart__svg"
        :width="width"
        :height="height"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="ariaLabel"
      >
        <g class="chart__grid">
          <template v-for="line in gridLines" :key="`grid-${line.y}`">
            <line
              :x1="PAD_LEFT"
              :x2="width - PAD_RIGHT"
              :y1="line.y"
              :y2="line.y"
              class="chart__grid-line"
            />
            <text :x="PAD_LEFT - 12" :y="line.y + 4" class="chart__axis-label" text-anchor="end">
              {{ formatMoneyCompactAxis(line.value) }}
            </text>
          </template>
        </g>

        <g class="chart__bars">
          <rect
            v-for="bar in bars"
            :key="`bar-${bar.key}`"
            :x="bar.x"
            :y="bar.y"
            :width="bar.width"
            :height="bar.height"
            rx="4"
            class="chart__bar"
          />
        </g>

        <g class="chart__x-labels">
          <text
            v-for="bar in bars"
            :key="`label-${bar.key}`"
            :x="bar.centerX"
            :y="height - 16"
            text-anchor="middle"
            class="chart__x-label"
          >
            {{ bar.item.label }}
          </text>
        </g>
      </svg>

      <!-- Линия рентабельности: отдельный SVG-компонент поверх столбцов -->
      <div class="chart__overlay">
        <slot name="overlay" :width="width" :height="height" v-bind="plot" />
      </div>

      <!-- Подсказка при наведении: невидимые полосы по числу месяцев, a-tooltip Ant Design Vue -->
      <div class="chart__hover">
        <a-tooltip
          v-for="bar in bars"
          :key="`hit-${bar.key}`"
          placement="top"
          :mouse-enter-delay="0.05"
        >
          <template #title>
            <div class="tip">
              <div class="tip__title">{{ bar.item.title ?? bar.item.label }}</div>
              <div class="tip__row">
                <span>{{ valueLabel }}</span>
                <span>{{ valueFormatter(bar.value) }}</span>
              </div>
              <div v-for="line in bar.item.lines ?? []" :key="line.label" class="tip__row">
                <span>{{ line.label }}</span>
                <span>{{ line.value }}</span>
              </div>
            </div>
          </template>
          <div class="chart__hit" :style="bandStyle(bar.index)"></div>
        </a-tooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart {
  width: 100%;
}

.chart__stack {
  position: relative;
  width: 100%;
  overflow: hidden;
}

.chart__svg {
  display: block;
}

.chart__overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.chart__hover {
  position: absolute;
  inset: 0;
}

.chart__hit {
  position: absolute;
  cursor: default;
}

.chart__hit:hover {
  background: rgb(47 111 168 / 6%);
}

.chart__grid-line {
  stroke: #eef1f5;
  stroke-width: 1;
}

.chart__axis-label {
  font-size: 12px;
  fill: #8c8c8c;
  font-family: 'Inter', sans-serif;
}

.chart__bar {
  fill: #2f6fa8;
  transition:
    height 0.25s ease,
    y 0.25s ease;
}

.chart__x-label {
  font-size: 12px;
  fill: #595959;
  font-family: 'Inter', sans-serif;
}

.chart__empty {
  margin: 0;
  padding: 24px 0;
  text-align: center;
  color: #8c8c8c;
}

.tip {
  min-width: 150px;
  font-size: 13px;
}

.tip__title {
  font-weight: 600;
  margin-bottom: 4px;
}

.tip__row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  white-space: nowrap;
}
</style>
