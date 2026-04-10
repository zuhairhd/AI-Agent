<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Calls</h1>
        <p class="text-sm text-gray-500 mt-1">All inbound call sessions</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-400">Auto-refreshing every 10s</span>
        <button @click="doExportCsv"
                class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-700 hover:border-blue-300 transition">
          ⬇ Export CSV
        </button>
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
        <option value="ended_by_caller">Ended by Caller</option>
        <option value="abandoned">Abandoned</option>
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

    <!-- Bulk action bar -->
    <div v-if="selected.size > 0"
         class="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 flex items-center gap-3 text-sm">
      <span class="text-blue-700 font-medium">{{ selected.size }} selected</span>
      <button @click="doBulkMark(true)"
              class="px-3 py-1.5 rounded-lg border border-orange-300 text-orange-700 hover:bg-orange-50 transition">
        Flag Follow-up
      </button>
      <button @click="doBulkMark(false)"
              class="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 transition">
        Clear Follow-up
      </button>
      <button @click="confirmBulkDelete = true"
              class="px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition">
        Delete Selected
      </button>
      <button @click="selected.clear(); selected = new Set()"
              class="ml-auto px-3 py-1.5 text-gray-500 hover:text-gray-700">
        Deselect all
      </button>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th class="px-4 py-3 w-8">
              <input type="checkbox" :checked="allSelected" @change="toggleAll"
                     class="rounded border-gray-300" />
            </th>
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
            <td colspan="7" class="text-center py-12 text-gray-400">No calls found.</td>
          </tr>
          <tr v-for="call in calls" :key="call.id"
              class="border-b border-gray-50 hover:bg-gray-50 transition-colors"
              :class="selected.has(call.id) ? 'bg-blue-50' : ''">
            <td class="px-4 py-3" @click.stop>
              <input type="checkbox" :checked="selected.has(call.id)"
                     @change="toggleOne(call.id)"
                     class="rounded border-gray-300" />
            </td>
            <td class="px-4 py-3 font-medium text-gray-800 cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)">{{ call.caller_number }}</td>
            <td class="px-4 py-3 text-gray-600 cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)">{{ fmt(call.started_at) }}</td>
            <td class="px-4 py-3 text-gray-600 cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)">{{ fmtDur(call.duration_seconds) }}</td>
            <td class="px-4 py-3 cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)"><StatusBadge :status="call.status" /></td>
            <td class="px-4 py-3 text-gray-600 uppercase text-xs cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)">{{ call.language }}</td>
            <td class="px-4 py-3 flex gap-1 flex-wrap cursor-pointer"
                @click="$router.push(`/portal/calls/${call.id}`)">
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

    <!-- Bulk delete confirmation modal -->
    <div v-if="confirmBulkDelete" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
        <h3 class="font-semibold text-gray-900 mb-2">Delete {{ selected.size }} Call(s)?</h3>
        <p class="text-sm text-gray-600 mb-4">
          This will permanently delete the selected sessions and all associated audio files. This cannot be undone.
        </p>
        <div class="flex justify-end gap-3">
          <button @click="confirmBulkDelete = false"
                  class="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-700">Cancel</button>
          <button @click="doBulkDelete"
                  class="px-4 py-2 text-sm text-white rounded-lg bg-red-500 hover:bg-red-600 transition">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getCalls, bulkDeleteCalls, bulkMarkCalls, exportCallsCsv } from '@/api/calls'
import { useUiStore } from '@/stores/ui'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const uiStore = useUiStore()
const calls   = ref([])
const loading = ref(true)
const count   = ref(0)
const next    = ref(null)
const prev    = ref(null)
const page    = ref(1)
const filters = ref({ search:'', status:'', needs_followup:'', date_from:'', date_to:'' })

// Bulk selection
let selected         = ref(new Set())
const confirmBulkDelete = ref(false)

const allSelected = computed(() =>
  calls.value.length > 0 && calls.value.every(c => selected.value.has(c.id))
)

function toggleOne(id) {
  const s = new Set(selected.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selected.value = s
}

function toggleAll() {
  if (allSelected.value) {
    selected.value = new Set()
  } else {
    selected.value = new Set(calls.value.map(c => c.id))
  }
}

let pollTimer     = null

onUnmounted(() => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } })

let debounceTimer = null
function debounceLoad() { clearTimeout(debounceTimer); debounceTimer = setTimeout(load, 400) }

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const params = { page: page.value, ...Object.fromEntries(Object.entries(filters.value).filter(([,v]) => v !== '')) }
    const res = (await getCalls(params)).data
    calls.value = res.results || res
    count.value = res.count ?? calls.value.length
    next.value  = res.next
    prev.value  = res.previous
  } finally { if (!silent) loading.value = false }
}

function goPage(p) { page.value = p; load() }

onMounted(() => {
  load()
  pollTimer = setInterval(() => load(true), 10000)
})

async function doBulkDelete() {
  confirmBulkDelete.value = false
  try {
    const ids = [...selected.value]
    await bulkDeleteCalls(ids)
    selected.value = new Set()
    uiStore.addToast(`Deleted ${ids.length} call(s).`, 'success')
    load()
  } catch { uiStore.addToast('Bulk delete failed.', 'error') }
}

async function doBulkMark(flag) {
  try {
    const ids = [...selected.value]
    await bulkMarkCalls(ids, flag)
    selected.value = new Set()
    uiStore.addToast(`Updated ${ids.length} call(s).`, 'success')
    load()
  } catch { uiStore.addToast('Bulk update failed.', 'error') }
}

async function doExportCsv() {
  try {
    const params = Object.fromEntries(Object.entries(filters.value).filter(([,v]) => v !== ''))
    const res = await exportCallsCsv(params)
    const url = URL.createObjectURL(res.data)
    const a   = document.createElement('a')
    a.href    = url
    a.download = 'calls_export.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch { uiStore.addToast('Export failed.', 'error') }
}

function fmt(s) { return s ? new Date(s).toLocaleString() : '—' }
function fmtDur(s) {
  if (s === null || s === undefined) return '—'
  return `${Math.floor(s/60)}m ${s%60}s`
}
</script>
