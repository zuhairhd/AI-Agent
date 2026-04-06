<template>
  <span class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold uppercase" :class="classes">
    {{ severity }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ severity: String })
const classes = computed(() => ({
  'bg-red-100 text-red-700':     props.severity === 'high',
  'bg-yellow-100 text-yellow-700': props.severity === 'medium',
  'bg-green-100 text-green-700': props.severity === 'low',
}))
</script>
