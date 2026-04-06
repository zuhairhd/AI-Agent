<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Calls</h1>
        <p class="text-sm text-gray-500 mt-1">All inbound call sessions</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 mb-4 flex flex-wrap gap-3">
      <input v-model="filters.search" @input="debounceLoad" placeholder="Search caller..."
             class="border border-gray-200 rounded-lg px-3 py-2 text-sm w-44" />
      <select v-model="filters.status" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
        <option value="">All Statuses</option>
        <option value="active">Active</option>
        <option value="completed">Completed</option>
        <option value="failed">Failed</option>
        <option value="transferred">Transferred</option>
      </select>
      <select v-model="filters.needs_followup" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
        <option value="">All</option>
        <option value="true">Needs Follow-up</option>
        <option value="false">No Follow-up</option>
      </select>
      <input v-model="filters.date_from" type="date" @change="load"
             class="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
      <input v-model="filters.date_to" type="date" @change="load"
             class="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Caller</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Date / Time</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Duration</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Status</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Language</th>
            <th class="text-left px-4 py-3 font-semibold text-gray-600">Flags</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="calls.length === 0">
            <td colspan="6" class="text-center py-12 text-gray-400">No calls found.</td>
          </tr>
          <tr v-for="call in calls" :key="call.id"
              class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
              @click="$router.push(`/portal/calls/${call.id}`)">
            <td class="px-4 py-3 font-medium text-gray-800">{{ call.caller_number }}</td>
            <td class="px-4 py-3 text-gray-600">{{ fmt(call.started_at) }}</td>
            <td class="px-4 py-3 text-gray-600">{{ fmtDur(call.duration_seconds) }}</td>
            <td class="px-4 py-3"><StatusBadge :status="call.status" /></td>
            <td class="px-4 py-3 text-gray-600 uppercase text-xs">{{ call.language }}</td>
            <td class="px-4 py-3 flex gap-1 flex-wrap">
              <span v-if="call.needs_followup" class="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">Follow-up</span>
              <span v-if="call.transfer_triggered" class="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">Escalated</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="px-4 py-3 flex items-center justify-between border-t border-gray-100">
        <span class="text-sm text-gray-500">{{ count }} total</span>
        <div class="flex gap-2">
          <button :disabled="!prev" @click="goPage(page-1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Prev</button>
          <span class="px-3 py-1.5 text-sm text-gray-600">{{ page }}</span>
          <button :disabled="!next" @click="goPage(page+1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCalls } from '@/api/calls'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const calls   = ref([])
const loading = ref(true)
const count   = ref(0)
const next    = ref(null)
const prev    = ref(null)
const page    = ref(1)
const filters = ref({ search:'', status:'', needs_followup:'', date_from:'', date_to:'' })

let debounceTimer = null
function debounceLoad() { clearTimeout(debounceTimer); debounceTimer = setTimeout(load, 400) }

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, ...Object.fromEntries(Object.entries(filters.value).filter(([,v]) => v !== '')) }
    const res = (await getCalls(params)).data
    calls.value = res.results || res
    count.value = res.count ?? calls.value.length
    next.value  = res.next
    prev.value  = res.previous
  } finally { loading.value = false }
}

function goPage(p) { page.value = p; load() }
onMounted(load)

function fmt(s) { return s ? new Date(s).toLocaleString() : '—' }
function fmtDur(s) {
  if (s === null || s === undefined) return '—'
  return `${Math.floor(s/60)}m ${s%60}s`
}
</script>
