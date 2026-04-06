<template>
  <div>
    <div class="mb-6">
      <h1 class="text-xl font-bold text-gray-900">Dashboard</h1>
      <p class="text-sm text-gray-500 mt-1">Today's call overview — {{ today }}</p>
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <!-- KPI Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
        <KpiCard label="Total Calls"     :value="data?.kpis?.total_today"      icon="📞" />
        <KpiCard label="Resolved"        :value="data?.kpis?.resolved_today"    icon="✅" />
        <KpiCard label="Unresolved"      :value="data?.kpis?.unresolved_today"  icon="⚠️" />
        <KpiCard label="Needs Follow-up" :value="data?.kpis?.followup_today"    icon="📋" />
        <KpiCard label="Escalated"       :value="data?.kpis?.escalated_today"   icon="🔺" />
        <KpiCard label="Avg Duration"    :value="formatDuration(data?.kpis?.avg_duration_seconds)" icon="⏱" />
      </div>

      <!-- Recent Alerts -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h2 class="text-sm font-semibold text-gray-700 mb-4">Recent Open Alerts</h2>
          <div v-if="data?.recent_alerts?.length === 0" class="text-sm text-gray-400">No open alerts.</div>
          <div v-for="alert in data?.recent_alerts" :key="alert.id" class="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0">
            <SeverityBadge :severity="alert.severity" />
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-800 truncate">{{ alert.title }}</div>
              <div class="text-xs text-gray-400">{{ formatDate(alert.created_at) }}</div>
            </div>
          </div>
          <router-link to="/portal/alerts" class="text-xs mt-3 block" style="color: var(--fss-bronze)">View all alerts →</router-link>
        </div>

        <!-- Recent Calls -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h2 class="text-sm font-semibold text-gray-700 mb-4">Recent Calls</h2>
          <div v-for="call in data?.recent_calls" :key="call.id"
               class="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0 cursor-pointer hover:bg-gray-50 rounded"
               @click="$router.push(`/portal/calls/${call.id}`)">
            <StatusBadge :status="call.status" />
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-800">{{ call.caller_number }}</div>
              <div class="text-xs text-gray-400">{{ formatDate(call.started_at) }}</div>
            </div>
            <div v-if="call.needs_followup" class="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Follow-up</div>
          </div>
          <router-link to="/portal/calls" class="text-xs mt-3 block" style="color: var(--fss-bronze)">View all calls →</router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDashboard } from '@/api/dashboard'
import KpiCard from '@/components/ui/KpiCard.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import SeverityBadge from '@/components/ui/SeverityBadge.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const data    = ref(null)
const loading = ref(true)
const today   = new Date().toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' })

onMounted(async () => {
  try { data.value = (await getDashboard()).data }
  finally { loading.value = false }
})

function formatDate(s) { return s ? new Date(s).toLocaleString() : '—' }
function formatDuration(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60), sec = s % 60
  return `${m}m ${sec}s`
}
</script>
