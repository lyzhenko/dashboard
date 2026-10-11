<script setup lang="ts">
import { computed, watch } from 'vue'

import type { Organization } from '@/api/dashboard'

/** Явный пункт «Все организации»: organization = null в запросах. */
const ALL_ORGANIZATIONS = '__all__'

const props = withDefaults(
  defineProps<{
    items: Organization[] | null | undefined
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    loading: false,
    disabled: false,
  },
)

const model = defineModel<string | null>({ required: true })

const organizations = computed(() => props.items ?? [])

const options = computed(() => [
  { value: ALL_ORGANIZATIONS, label: 'Все организации' },
  ...organizations.value.map((organization) => ({
    value: organization.id,
    label: organization.name,
  })),
])

/**
 * По умолчанию — «Все организации» (контракт, 1.2).
 * Организация выбирается сама только тогда, когда она в базе одна: isDefault = true
 * у единственной организации, и дашборд сразу показывает её данные.
 */
watch(
  organizations,
  (list) => {
    const only = list.length === 1 ? list[0] : undefined
    if (model.value === null && only?.isDefault) {
      model.value = only.id
    }
  },
  { immediate: true },
)

function onChange(value: unknown): void {
  if (typeof value !== 'string' || value === ALL_ORGANIZATIONS || value === '') {
    model.value = null
    return
  }
  model.value = value
}
</script>

<template>
  <a-select
    class="organization-select"
    data-testid="organization-select"
    :value="model ?? ALL_ORGANIZATIONS"
    :options="options"
    :loading="loading"
    :disabled="disabled"
    show-search
    option-filter-prop="label"
    style="min-width: 240px"
    @change="onChange"
  />
</template>

<style scoped>
.organization-select {
  max-width: 340px;
}
</style>
