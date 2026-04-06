<template>
  <div v-if="score !== null && score !== undefined" class="flex items-center gap-2">
    <div class="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
      <div
        class="h-2 rounded-full transition-all duration-500"
        :style="{ width: pct + '%', background: color }"
      ></div>
    </div>
    <span class="text-xs font-medium w-10 text-right" :style="{ color }">{{ pct }}%</span>
  </div>
  <span v-else class="text-xs text-gray-400">—</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ score: Number })  // 0.0–1.0

const pct   = computed(() => props.score !== null && props.score !== undefined
  ? Math.round(props.score * 100) : 0)

const color = computed(() => {
  const p = pct.value
  if (p >= 75) return '#10B981'   // green
  if (p >= 50) return '#F59E0B'   // amber
  return '#EF4444'                // red
})
</script>
