<script setup lang="ts">
import { computed } from 'vue'

import { formatAge, formatIsoDateTime } from '@/composables/useMoneyFormat'

const props = withDefaults(
  defineProps<{
    /** Признак из meta.stale: данные старше KPI_CACHE_TTL_SECONDS. */
    stale: boolean
    fetchedAt?: string | null
    ageSeconds?: number | null
    loading?: boolean
  }>(),
  {
    fetchedAt: null,
    ageSeconds: null,
    loading: false,
  },
)

const emit = defineEmits<{ refresh: [] }>()

const description = computed(() => {
  const facts: string[] = []
  if (props.fetchedAt) {
    facts.push(`Данные получены ${formatIsoDateTime(props.fetchedAt)}`)
  }
  if (props.ageSeconds !== null && props.ageSeconds !== undefined) {
    facts.push(`возраст ${formatAge(props.ageSeconds)}`)
  }
  const head = facts.length > 0 ? `${facts.join(', ')}. ` : ''
  return `${head}Показатели могут не отражать последние операции в 1С.`
})
</script>

<template>
  <a-alert
    v-if="stale"
    class="stale-banner"
    data-testid="stale-banner"
    type="warning"
    show-icon
    message="Данные устарели"
  >
    <template #description>
      <div class="stale-banner__body">
        <span class="stale-banner__text">{{ description }}</span>
        <a-button size="small" :loading="loading" @click="emit('refresh')">Обновить</a-button>
      </div>
    </template>
  </a-alert>
</template>

<style scoped>
.stale-banner {
  margin-bottom: 16px;
}

.stale-banner__body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.stale-banner__text {
  font-size: 13px;
}
</style>
