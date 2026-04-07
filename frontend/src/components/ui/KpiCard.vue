<template>
  <div
    class="group relative overflow-hidden rounded-2xl border border-white/10 p-5 shadow-[0_10px_30px_rgba(0,0,0,.18)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_16px_38px_rgba(0,0,0,.26)]"
    style="background: linear-gradient(160deg, rgba(12,29,52,.97) 0%, rgba(10,24,45,.95) 100%);"
  >
    <!-- Subtle background glow -->
    <div
      class="pointer-events-none absolute -right-6 -top-6 h-28 w-28 rounded-full opacity-10 blur-2xl transition-opacity duration-300 group-hover:opacity-20"
      style="background: radial-gradient(circle, var(--fss-bronze), transparent 70%);"
    ></div>

    <div class="relative flex items-start justify-between gap-3">
      <!-- Icon -->
      <div
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 text-xl"
        style="background: rgba(196,146,102,.10);"
      >
        {{ icon }}
      </div>

      <!-- Trend badge -->
      <span
        v-if="trend !== undefined"
        class="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold"
        :class="trend >= 0
          ? 'bg-emerald-400/10 text-emerald-400'
          : 'bg-red-400/10 text-red-400'"
      >{{ trend >= 0 ? '+' : '' }}{{ trend }}%</span>
    </div>

    <div class="relative mt-4">
      <div class="text-3xl font-bold tracking-tight text-white">{{ value ?? '—' }}</div>
      <div class="mt-1 text-sm font-medium text-slate-400">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [Number, String],
  icon:  String,
  trend: Number,
})
</script>
