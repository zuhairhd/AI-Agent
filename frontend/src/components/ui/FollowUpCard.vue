<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
    <div class="flex items-start justify-between gap-3">
      <!-- Left -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-semibold text-gray-800 text-sm">{{ followup.session_caller || followup.session }}</span>
          <SeverityBadge :severity="followup.priority" />
          <StatusBadge   :status="followup.status" :label="followup.status.replace('_',' ')" />
        </div>
        <div class="text-xs text-gray-400 mt-0.5">Created {{ fmt(followup.created_at) }}</div>
        <div v-if="followup.due_date" class="text-xs text-orange-600 mt-0.5">
          Due {{ fmt(followup.due_date) }}
        </div>
        <div v-if="followup.notes" class="text-sm text-gray-600 mt-2 line-clamp-2">{{ followup.notes }}</div>
      </div>

      <!-- Actions -->
      <div class="flex flex-col items-end gap-2 flex-shrink-0">
        <router-link :to="`/portal/calls/${followup.session}`"
                     class="text-xs hover:underline" style="color: var(--fss-bronze)">
          View Call
        </router-link>
        <button
          v-if="followup.status !== 'completed'"
          @click="$emit('complete', followup)"
          class="text-xs px-2.5 py-1 rounded border border-green-200 text-green-700 hover:bg-green-50 transition-colors"
        >Mark Complete</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import SeverityBadge from './SeverityBadge.vue'
import StatusBadge   from './StatusBadge.vue'

defineProps({ followup: Object })
defineEmits(['complete'])
function fmt(s) { return s ? new Date(s).toLocaleString() : '—' }
</script>
