<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex items-start gap-4">
    <SeverityBadge :severity="alert.severity" />

    <div class="flex-1 min-w-0">
      <div class="font-semibold text-gray-800 text-sm truncate">{{ alert.title }}</div>
      <div class="text-xs text-gray-400 mt-0.5">
        {{ alert.alert_type }} &bull; {{ fmt(alert.created_at) }}
      </div>
      <div v-if="alert.description" class="text-sm text-gray-600 mt-1">{{ alert.description }}</div>
      <div class="mt-2">
        <EmailSentIndicator
          :sent="alert.email_sent"
          :pending="alert.send_email && !alert.email_sent"
          :sent-at="alert.email_sent_at"
        />
      </div>
    </div>

    <div class="flex flex-col items-end gap-2 flex-shrink-0">
      <StatusBadge :status="alert.status" :label="alert.status" />
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import SeverityBadge    from './SeverityBadge.vue'
import StatusBadge      from './StatusBadge.vue'
import EmailSentIndicator from './EmailSentIndicator.vue'

defineProps({ alert: Object })
function fmt(s) { return s ? new Date(s).toLocaleString() : '—' }
</script>
