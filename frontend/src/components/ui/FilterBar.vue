<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex flex-wrap gap-3 items-center">
    <slot />
    <button
      v-if="showReset"
      @click="$emit('reset')"
      class="text-xs px-3 py-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50"
    >Reset</button>
  </div>
</template>

<script setup>
defineProps({ showReset: { type: Boolean, default: false } })
defineEmits(['reset'])
</script>
