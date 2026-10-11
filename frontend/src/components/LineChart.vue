<script setup lang="ts">
import { computed } from 'vue'

/**
 * Линия рентабельности поверх столбцов выручки.
 *
 * Геометрия области построения приходит из BarChart (слот overlay): обе диаграммы
 * рисуются в одной системе координат, поэтому полосы месяцев совпадают.
 * Компонент самодостаточен — значения по умолчанию совпадают с геометрией BarChart.
 */
const props = withDefaults(
  defineProps<{
    /** Значения по месяцам; null — нет данных за месяц (разрыв линии). */
    values: (number | null)[]
    width?: number
    height?: number
    plotTop?: number
    plotBottom?: number
    plotLeft?: number
    plotRight?: number
    color?: string
    /** Толщина линии. */
    strokeWidth?: number
    showPoints?: boolean
  }>(),
  {
    width: 720,
    height: 280,
    plotTop: 20,
    plotBottom: 44,
    plotLeft: 84,
    plotRight: 20,
    color: '#d4770b',
    strokeWidth: 2,
    showPoints: true,
  },
)

const plotHeight = computed(() => Math.max(1, props.height - props.plotTop - props.plotBottom))
const plotWidth = computed(() => Math.max(1, props.width - props.plotLeft - props.plotRight))

const domain = computed(() => {
  const finite = props.values.filter(
    (value): value is number => typeof value === 'number' && Number.isFinite(value),
  )
  if (finite.length === 0) {
    return null
  }
  // Ноль всегда в области значений: рентабельность читается относительно нуля
  const min = Math.min(0, ...finite)
  const max = Math.max(0, ...finite)
  return { min, max, span: max - min || 1 }
})

const points = computed(() => {
  const scale = domain.value
  if (!scale) {
    return []
  }
  const band = plotWidth.value / Math.max(1, props.values.length)
  return props.values.map((value, index) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return null
    }
    return {
      index,
      value,
      x: props.plotLeft + band * (index + 0.5),
      y: props.plotTop + plotHeight.value * (1 - (value - scale.min) / scale.span),
    }
  })
})

/** Точки без разрывов — для маркеров. */
const pointMarks = computed(() =>
  points.value.filter((point): point is NonNullable<typeof point> => point !== null),
)

/** Непрерывные участки: null разрывает линию. */
const segments = computed(() => {
  const result: { x: number; y: number }[][] = []
  let current: { x: number; y: number }[] = []
  for (const point of points.value) {
    if (point) {
      current.push({ x: point.x, y: point.y })
    } else if (current.length > 0) {
      result.push(current)
      current = []
    }
  }
  if (current.length > 0) {
    result.push(current)
  }
  return result
})

function toPolyline(segment: { x: number; y: number }[]): string {
  return segment.map((point) => `${point.x},${point.y}`).join(' ')
}
</script>

<template>
  <svg
    class="line-chart"
    :width="width"
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    role="img"
    aria-label="Рентабельность по месяцам"
    data-testid="line-chart"
  >
    <polyline
      v-for="(segment, index) in segments"
      :key="`segment-${index}`"
      :points="toPolyline(segment)"
      fill="none"
      :stroke="color"
      :stroke-width="strokeWidth"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
    <template v-if="showPoints">
      <circle
        v-for="point in pointMarks"
        :key="`point-${point.index}`"
        :cx="point.x"
        :cy="point.y"
        r="3"
        :fill="color"
      />
    </template>
  </svg>
</template>

<style scoped>
.line-chart {
  display: block;
  overflow: visible;
}
</style>
