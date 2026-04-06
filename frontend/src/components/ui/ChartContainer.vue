<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-700">{{ title }}</h3>
      <slot name="actions" />
    </div>
    <LoadingSpinner v-if="loading" />
    <div v-else-if="$slots.default" class="relative">
      <slot />
    </div>
    <EmptyState v-else icon="📊" title="No data" message="Not enough data to display chart." />
  </div>
</template>

<script setup>
import LoadingSpinner from './LoadingSpinner.vue'
import EmptyState from './EmptyState.vue'
defineProps({ title: String, loading: Boolean })
</script>
