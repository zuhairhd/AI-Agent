<template>
  <span class="inline-flex items-center gap-1 text-xs">
    <span v-if="sent" class="text-green-600">✉️ Sent{{ sentAt ? ' ' + fmt(sentAt) : '' }}</span>
    <span v-else-if="pending" class="text-yellow-600">✉️ Pending</span>
    <span v-else class="text-gray-400">No email</span>
  </span>
</template>

<script setup>
const props = defineProps({
  sent:    Boolean,
  pending: Boolean,
  sentAt:  String,
})
function fmt(s) {
  if (!s) return ''
  return new Date(s).toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })
}
</script>
