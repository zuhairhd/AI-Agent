<template>
  <div class="text-center py-16 text-gray-400">
    <div class="text-4xl mb-3">{{ icon }}</div>
    <div class="font-medium text-gray-600 mb-1">{{ title }}</div>
    <div class="text-sm">{{ message }}</div>
  </div>
</template>
<script setup>
defineProps({ icon: { default: '📭' }, title: String, message: String })
</script>
