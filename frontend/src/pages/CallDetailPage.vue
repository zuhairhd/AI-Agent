<template>
  <div>
    <button @click="$router.back()" class="text-sm mb-4 flex items-center gap-1" style="color: var(--fss-bronze)">
      ← Back to Calls
    </button>

    <LoadingSpinner v-if="loading" />

    <template v-else-if="call">
      <!-- Header -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-xl font-bold text-gray-900">{{ call.caller_number }}</h1>
            <p class="text-sm text-gray-500 mt-1">{{ fmt(call.started_at) }} · {{ fmtDur(call.duration_seconds) }}</p>
          </div>
          <div class="flex gap-2 flex-wrap">
            <StatusBadge :status="call.status" />
            <span v-if="call.needs_followup" class="bg-orange-100 text-orange-700 text-xs px-2.5 py-1 rounded-full font-semibold">
              Follow-up Needed
            </span>
          </div>
        </div>

        <!-- Flags -->
        <div class="flex flex-wrap gap-2 mt-4">
          <span v-if="call.transfer_triggered" class="bg-red-50 text-red-700 border border-red-200 text-xs px-2.5 py-1 rounded-full">
            🔺 Escalated — {{ call.transfer_reason }}
          </span>
          <span v-if="call.total_turns === 0" class="bg-yellow-50 text-yellow-700 border border-yellow-200 text-xs px-2.5 py-1 rounded-full">
            ⚠️ No conversation turns
          </span>
          <span class="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full">
            Lang: {{ call.language?.toUpperCase() }}
          </span>
          <span class="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full">
            Turns: {{ call.total_turns }}
          </span>
        </div>

        <!-- Actions -->
        <div class="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-100">
          <button @click="doExport"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 text-gray-700 hover:border-blue-300 transition flex items-center gap-1">
            ⬇ Export ZIP
          </button>
          <button @click="confirmDeleteModal = true"
                  class="px-3 py-1.5 text-sm rounded-lg border border-red-100 text-red-500 hover:bg-red-50 transition">
            🗑 Delete Call
          </button>
        </div>
      </div>

      <!-- Transcript -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4">
        <h2 class="text-sm font-semibold text-gray-700 mb-4">Conversation</h2>
        <TranscriptViewer :turns="call.turns" />
      </div>

      <!-- Staff Notes -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4">
        <h2 class="text-sm font-semibold text-gray-700 mb-3">Staff Notes</h2>
        <textarea
          v-model="notes"
          rows="3"
          placeholder="Add internal notes about this call…"
          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-none"
        ></textarea>
        <div class="flex gap-3 mt-3">
          <button @click="saveNotes" class="px-4 py-2 text-sm text-white rounded-lg"
                  style="background: var(--fss-bronze)">Save Notes</button>
          <button @click="toggleFollowup" class="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-700">
            {{ call.needs_followup ? 'Remove Follow-up Flag' : 'Flag for Follow-up' }}
          </button>
        </div>
      </div>
    </template>

    <EmptyState v-else title="Call not found" message="This call session could not be loaded." />

    <!-- Delete confirmation modal -->
    <div v-if="confirmDeleteModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
        <h3 class="font-semibold text-gray-900 mb-2">Delete Call</h3>
        <p class="text-sm text-gray-600 mb-4">
          This will permanently delete this call session and all associated audio files. This cannot be undone.
        </p>
        <div class="flex justify-end gap-3">
          <button @click="confirmDeleteModal = false" class="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-700">Cancel</button>
          <button @click="doDelete" class="px-4 py-2 text-sm text-white rounded-lg bg-red-500 hover:bg-red-600 transition">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCall, patchCall, exportCall, deleteCall } from '@/api/calls'
import { useUiStore } from '@/stores/ui'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TranscriptViewer from '@/components/ui/TranscriptViewer.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const route   = useRoute()
const router  = useRouter()
const uiStore = useUiStore()
const call    = ref(null)
const loading = ref(true)
const notes   = ref('')
const confirmDeleteModal = ref(false)

onMounted(async () => {
  try {
    call.value = (await getCall(route.params.id)).data
    notes.value = call.value.staff_notes || ''
  } finally { loading.value = false }
})

async function saveNotes() {
  try {
    await patchCall(call.value.id, { staff_notes: notes.value })
    uiStore.addToast('Notes saved.', 'success')
  } catch { uiStore.addToast('Failed to save notes.', 'error') }
}

async function toggleFollowup() {
  try {
    const res = await patchCall(call.value.id, { needs_followup: !call.value.needs_followup })
    call.value.needs_followup = res.data.needs_followup
    uiStore.addToast('Follow-up flag updated.', 'success')
  } catch { uiStore.addToast('Failed to update flag.', 'error') }
}

async function doExport() {
  try {
    const res = await exportCall(call.value.id)
    const url = URL.createObjectURL(res.data)
    const a   = document.createElement('a')
    a.href    = url
    a.download = `call_${call.value.caller_number}_${call.value.id}.zip`
    a.click()
    URL.revokeObjectURL(url)
  } catch { uiStore.addToast('Export failed.', 'error') }
}

async function doDelete() {
  confirmDeleteModal.value = false
  try {
    await deleteCall(call.value.id)
    uiStore.addToast('Call deleted.', 'success')
    router.push('/portal/calls')
  } catch { uiStore.addToast('Delete failed.', 'error') }
}

function fmt(s) { return s ? new Date(s).toLocaleString() : '—' }
function fmtDur(s) {
  if (s === null || s === undefined) return '—'
  return `${Math.floor(s/60)}m ${s%60}s`
}
</script>
