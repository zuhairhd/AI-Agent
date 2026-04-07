<template>
  <div>
    <h1 class="text-xl font-bold text-gray-900 mb-6">Follow-ups</h1>

    <FilterBar class="mb-4">
      <select v-model="filters.status" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="assigned">Assigned</option>
        <option value="in_progress">In Progress</option>
        <option value="completed">Completed</option>
        <option value="resolved">Resolved</option>
        <option value="closed">Closed</option>
      </select>
      <select v-model="filters.priority" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
        <option value="">All Priorities</option>
        <option value="urgent">Urgent</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <select v-model="filters.sla_breached" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
        <option value="">All SLA</option>
        <option value="true">SLA Breached</option>
        <option value="false">On Time</option>
      </select>
    </FilterBar>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <EmptyState v-if="followups.length === 0" icon="📋" title="No follow-ups" message="No follow-up tasks match the current filters." />

      <div v-else class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              <th class="px-4 py-3 text-left">Caller</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Priority</th>
              <th class="px-4 py-3 text-left">Assigned</th>
              <th class="px-4 py-3 text-left">SLA Deadline</th>
              <th class="px-4 py-3 text-left">Time Remaining</th>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <tr v-for="fu in followups" :key="fu.id" class="hover:bg-gray-50 transition">
              <td class="px-4 py-3">
                <div class="font-medium text-gray-900">{{ fu.session_caller || '—' }}</div>
                <div class="text-xs text-gray-400">{{ fmtDate(fu.created_at) }}</div>
              </td>
              <td class="px-4 py-3">
                <span :class="statusClass(fu.status)"
                      class="px-2 py-0.5 rounded-full text-xs font-semibold">
                  {{ fu.status }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span :class="priorityClass(fu.priority)"
                      class="px-2 py-0.5 rounded-full text-xs font-semibold">
                  {{ fu.priority }}
                </span>
              </td>
              <td class="px-4 py-3 text-gray-600">
                {{ fu.assigned_to ? fu.assigned_to.username : '—' }}
              </td>
              <td class="px-4 py-3 text-gray-600">{{ fmtDate(fu.sla_deadline) }}</td>
              <td class="px-4 py-3">
                <SlaCountdown :deadline="fu.sla_deadline" :breached="fu.sla_breached" />
              </td>
              <td class="px-4 py-3 text-right">
                <div class="flex justify-end gap-2">
                  <button v-if="fu.status === 'pending' || fu.status === 'assigned'"
                          @click="markInProgress(fu)"
                          class="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition">
                    Start
                  </button>
                  <button v-if="fu.status !== 'completed' && fu.status !== 'closed'"
                          @click="markComplete(fu)"
                          class="text-xs px-2.5 py-1 rounded border border-green-200 text-green-600 hover:bg-green-50 transition">
                    Resolve
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between pt-4">
        <span class="text-sm text-gray-500">{{ count }} total</span>
        <div class="flex gap-2">
          <button :disabled="!prev" @click="goPage(page-1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Prev</button>
          <span class="px-3 py-1.5 text-sm text-gray-600">{{ page }}</span>
          <button :disabled="!next" @click="goPage(page+1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Next</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getFollowUps, patchFollowUp } from '@/api/followups'
import { useUiStore } from '@/stores/ui'
import FilterBar      from '@/components/ui/FilterBar.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import EmptyState     from '@/components/ui/EmptyState.vue'
import SlaCountdown   from '@/components/ui/SlaCountdown.vue'

const followups = ref([])
const loading   = ref(true)
const count     = ref(0)
const next      = ref(null)
const prev      = ref(null)
const page      = ref(1)
const filters   = ref({ status: '', priority: '', sla_breached: '' })
const uiStore   = useUiStore()

async function load() {
  loading.value = true
  try {
    const params = { page: page.value }
    Object.entries(filters.value).forEach(([k, v]) => { if (v) params[k] = v })
    const res    = (await getFollowUps(params)).data
    followups.value = res.results || res
    count.value     = res.count ?? followups.value.length
    next.value      = res.next
    prev.value      = res.previous
  } finally { loading.value = false }
}

async function markComplete(fu) {
  try {
    await patchFollowUp(fu.id, { status: 'resolved', completed_at: new Date().toISOString() })
    uiStore.addToast('Marked as resolved.', 'success')
    load()
  } catch { uiStore.addToast('Update failed.', 'error') }
}

async function markInProgress(fu) {
  try {
    await patchFollowUp(fu.id, { status: 'in_progress' })
    uiStore.addToast('Status updated to In Progress.', 'success')
    load()
  } catch { uiStore.addToast('Update failed.', 'error') }
}

function goPage(p) { page.value = p; load() }
function fmtDate(s) { return s ? new Date(s).toLocaleString() : '—' }

function statusClass(s) {
  return {
    pending:     'bg-gray-100 text-gray-600',
    assigned:    'bg-blue-100 text-blue-700',
    in_progress: 'bg-yellow-100 text-yellow-700',
    completed:   'bg-green-100 text-green-700',
    resolved:    'bg-green-100 text-green-700',
    closed:      'bg-gray-100 text-gray-500',
  }[s] || 'bg-gray-100 text-gray-600'
}

function priorityClass(p) {
  return {
    urgent: 'bg-red-100 text-red-700',
    high:   'bg-orange-100 text-orange-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low:    'bg-gray-100 text-gray-600',
  }[p] || 'bg-gray-100 text-gray-600'
}

onMounted(load)
</script>
