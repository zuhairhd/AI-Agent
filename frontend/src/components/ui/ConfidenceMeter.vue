<template>
  <div
    class="rounded-2xl border border-white/10 p-5 shadow-[0_10px_30px_rgba(0,0,0,.18)]"
    style="background: linear-gradient(160deg, rgba(12,29,52,.97) 0%, rgba(10,24,45,.95) 100%);"
  >
    <div class="mb-4 flex items-center justify-between gap-2">
      <h3 class="text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">
        AI Confidence
      </h3>
      <span
        class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
        :class="labelClass"
      >{{ label }}</span>
    </div>

    <!-- Arc gauge -->
    <div class="flex flex-col items-center py-2">
      <div class="relative flex items-center justify-center">
        <svg width="140" height="80" viewBox="0 0 140 80" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- Track arc -->
          <path
            d="M 10 75 A 60 60 0 0 1 130 75"
            stroke="rgba(255,255,255,0.07)"
            stroke-width="12"
            stroke-linecap="round"
            fill="none"
          />
          <!-- Filled arc -->
          <path
            d="M 10 75 A 60 60 0 0 1 130 75"
            :stroke="arcColor"
            stroke-width="12"
            stroke-linecap="round"
            fill="none"
            :stroke-dasharray="arcLength"
            :stroke-dashoffset="arcOffset"
            class="transition-all duration-700 ease-out"
          />
          <!-- Center dot -->
          <circle cx="70" cy="75" r="5" :fill="arcColor" class="transition-colors duration-500" />
        </svg>

        <!-- Score text -->
        <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1 text-center">
          <div class="text-2xl font-bold text-white leading-none">
            {{ displayScore }}%
          </div>
        </div>
      </div>

      <!-- Scale labels -->
      <div class="mt-3 flex w-full items-center justify-between px-1 text-[11px] text-slate-500">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>

    <!-- Threshold bands -->
    <div class="mt-4 grid grid-cols-3 gap-2 text-xs">
      <div class="rounded-xl border border-white/5 bg-white/3 px-2 py-1.5 text-center">
        <div class="font-semibold text-red-400">Low</div>
        <div class="mt-0.5 text-slate-500">0–50%</div>
      </div>
      <div class="rounded-xl border border-white/5 bg-white/3 px-2 py-1.5 text-center">
        <div class="font-semibold text-yellow-400">Medium</div>
        <div class="mt-0.5 text-slate-500">50–80%</div>
      </div>
      <div class="rounded-xl border border-white/5 bg-white/3 px-2 py-1.5 text-center">
        <div class="font-semibold text-emerald-400">High</div>
        <div class="mt-0.5 text-slate-500">80–100%</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: {
    type: Number,
    default: null,
  },
})

// Total arc length for a semicircle (r=60, half of 2πr = π*60 ≈ 188.5)
const TOTAL_ARC = 188.5

const displayScore = computed(() => {
  if (props.score === null || props.score === undefined) return '—'
  return Math.round(props.score * 100)
})

const normalised = computed(() => {
  if (props.score === null || props.score === undefined) return 0
  return Math.min(1, Math.max(0, props.score))
})

const arcOffset = computed(() => TOTAL_ARC - normalised.value * TOTAL_ARC)

const arcLength = computed(() => `${TOTAL_ARC} ${TOTAL_ARC}`)

const arcColor = computed(() => {
  const s = normalised.value
  if (s >= 0.8) return '#34d399'   // emerald
  if (s >= 0.5) return '#fbbf24'   // amber
  return '#f87171'                  // red
})

const label = computed(() => {
  const s = normalised.value
  if (props.score === null || props.score === undefined) return 'N/A'
  if (s >= 0.8) return 'High'
  if (s >= 0.5) return 'Medium'
  return 'Low'
})

const labelClass = computed(() => {
  const s = normalised.value
  if (props.score === null || props.score === undefined) return 'bg-white/10 text-slate-400'
  if (s >= 0.8) return 'bg-emerald-400/10 text-emerald-400'
  if (s >= 0.5) return 'bg-yellow-400/10 text-yellow-400'
  return 'bg-red-400/10 text-red-400'
})
</script>
