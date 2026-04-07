<template>
  <div
    class="group rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(10,24,45,.96),rgba(12,29,52,.92))] p-5 shadow-[0_10px_30px_rgba(0,0,0,.18)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_16px_38px_rgba(0,0,0,.24)]"
  >
    <div class="flex items-start gap-4">
      <!-- Left badge -->
      <div class="shrink-0">
        <SeverityBadge :severity="alert.severity" />
      </div>

      <!-- Main content -->
      <div class="min-w-0 flex-1">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="truncate text-base font-semibold text-white">
              {{ alert.title }}
            </div>

            <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
                {{ alert.alert_type || 'Alert' }}
              </span>
              <span>•</span>
              <span>{{ fmt(alert.created_at) }}</span>
            </div>
          </div>

          <div class="shrink-0">
            <StatusBadge :status="alert.status" :label="alert.status" />
          </div>
        </div>

        <div
          v-if="alert.description"
          class="mt-3 text-sm leading-6 text-slate-300"
        >
          {{ alert.description }}
        </div>

        <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
          <EmailSentIndicator
            :sent="alert.email_sent"
            :pending="alert.send_email && !alert.email_sent"
            :sent-at="alert.email_sent_at"
          />

          <div class="flex items-center gap-2">
            <slot name="actions" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import SeverityBadge from './SeverityBadge.vue'
import StatusBadge from './StatusBadge.vue'
import EmailSentIndicator from './EmailSentIndicator.vue'

defineProps({
  alert: {
    type: Object,
    required: true,
  },
})

function fmt(value) {
  return value ? new Date(value).toLocaleString() : '—'
}
</script>