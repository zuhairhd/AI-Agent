<template>
  <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold" :class="classes">
    {{ label || status }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ status: String, label: String })
const classes = computed(() => ({
  'bg-green-100 text-green-800':   props.status === 'completed',
  'bg-red-100   text-red-800':     props.status === 'failed',
  'bg-yellow-100 text-yellow-800': props.status === 'active' || props.status === 'processing',
  'bg-blue-100  text-blue-800':    props.status === 'transferred',
  'bg-orange-100 text-orange-800': props.status === 'ended_by_caller',
  'bg-purple-100 text-purple-800': props.status === 'abandoned',
  'bg-gray-100  text-gray-800':    !['completed','failed','active','processing','transferred','ended_by_caller','abandoned'].includes(props.status),
}))
</script>
