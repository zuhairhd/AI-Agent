<template>
  <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
    <div class="flex items-center justify-between mb-3">
      <span class="text-2xl">{{ icon }}</span>
      <span
        v-if="trend !== undefined"
        class="text-xs font-medium px-2 py-0.5 rounded-full"
        :class="trend >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
      >{{ trend >= 0 ? '+' : '' }}{{ trend }}%</span>
    </div>
    <div class="text-2xl font-bold text-gray-900">{{ value ?? '—' }}</div>
    <div class="text-sm text-gray-500 mt-1">{{ label }}</div>
  </div>
</template>

<script setup>
defineProps({ label: String, value: [Number, String], icon: String, trend: Number })
</script>
