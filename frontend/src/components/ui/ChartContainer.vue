<template>
  <div
    class="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(10,24,45,.96),rgba(12,29,52,.92))] p-5 shadow-[0_10px_30px_rgba(0,0,0,.18)]"
  >
    <div class="mb-4 flex items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">
          {{ title }}
        </h3>
        <p class="mt-1 text-xs text-slate-500">
          Analytics overview
        </p>
      </div>

      <div class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>

    <div class="min-h-[220px]">
      <LoadingSpinner v-if="loading" />

      <div v-else-if="$slots.default" class="relative">
        <slot />
      </div>

      <EmptyState
        v-else
        icon="📊"
        title="No data available"
        message="Not enough data is available to display this chart yet."
      />
    </div>
  </div>
</template>

<script setup>
import LoadingSpinner from './LoadingSpinner.vue'
import EmptyState from './EmptyState.vue'

defineProps({
  title: String,
  loading: Boolean,
})
</script>