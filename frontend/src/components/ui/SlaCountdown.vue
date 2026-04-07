<template>
  <span v-if="!deadline" class="text-gray-400 text-xs">—</span>
  <span v-else-if="breached" class="text-red-600 text-xs font-semibold">SLA Breached</span>
  <span v-else :class="colorClass" class="text-xs font-semibold">{{ displayText }}</span>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'

const props = defineProps({
  deadline: { type: String, default: null },
  breached: { type: Boolean, default: false },
})

const remaining = ref(0)
let timer = null

function update() {
  if (!props.deadline) return
  remaining.value = Math.max(0, Math.floor((new Date(props.deadline) - Date.now()) / 1000))
}

onMounted(() => { update(); timer = setInterval(update, 30000) })
onUnmounted(() => clearInterval(timer))

const displayText = computed(() => {
  const s = remaining.value
  if (s <= 0) return 'Expired'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
})

const colorClass = computed(() => {
  const s = remaining.value
  if (s <= 0)       return 'text-red-600'
  if (s < 3600)     return 'text-orange-500'
  if (s < 3600 * 4) return 'text-yellow-600'
  return 'text-green-600'
})
</script>
