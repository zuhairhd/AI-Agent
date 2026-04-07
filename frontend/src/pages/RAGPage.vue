<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-gray-900">Knowledge Base</h1>
      <label class="px-4 py-2 text-sm text-white rounded-lg cursor-pointer hover:opacity-90 transition"
             style="background: var(--fss-bronze)">
        Upload Files
        <input type="file" multiple accept=".pdf,.docx,.txt,.csv,.md"
               class="hidden" @change="onFileSelect" />
      </label>
    </div>

    <!-- Upload progress -->
    <div v-if="uploading" class="mb-4 bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-sm text-blue-700">
      Uploading {{ uploadingCount }} file(s)…
    </div>

    <!-- Upload results -->
    <div v-if="uploadResults.length" class="mb-4 space-y-2">
      <div v-for="r in uploadResults" :key="r.file"
           :class="r.status === 'uploaded' ? 'bg-green-50 text-green-800 border-green-200'
                 : r.status === 'duplicate' ? 'bg-yellow-50 text-yellow-800 border-yellow-200'
                 : 'bg-red-50 text-red-800 border-red-200'"
           class="border rounded-lg px-4 py-2 text-sm flex items-center gap-2">
        <span>{{ r.status === 'uploaded' ? '✓' : r.status === 'duplicate' ? '⚠' : '✗' }}</span>
        <span class="font-medium">{{ r.file }}</span>
        <span class="ml-auto text-xs opacity-70">{{ r.reason || r.status }}</span>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="flex gap-3 mb-4">
      <select v-model="filters.status" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="processing">Processing</option>
        <option value="indexed">Indexed</option>
        <option value="failed">Failed</option>
      </select>
      <input v-model="filters.search" @input="debouncedLoad" type="text"
             placeholder="Search by filename…"
             class="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1" />
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <EmptyState v-if="docs.length === 0" icon="📄" title="No documents"
                  message="Upload PDF, DOCX, TXT, or CSV files to build the knowledge base." />

      <div v-else class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              <th class="px-4 py-3 text-left">File</th>
              <th class="px-4 py-3 text-left">Type</th>
              <th class="px-4 py-3 text-left">Size</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Uploaded</th>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <tr v-for="doc in docs" :key="doc.id" class="hover:bg-gray-50 transition">
              <td class="px-4 py-3 max-w-xs">
                <div class="font-medium text-gray-900 truncate">{{ doc.original_name }}</div>
                <div class="text-xs text-gray-400 truncate">{{ doc.file_name }}</div>
              </td>
              <td class="px-4 py-3 text-gray-600 uppercase text-xs">{{ doc.file_extension }}</td>
              <td class="px-4 py-3 text-gray-600">{{ doc.file_size_display }}</td>
              <td class="px-4 py-3">
                <span :class="statusClass(doc.sync_status)"
                      class="px-2 py-0.5 rounded-full text-xs font-semibold">
                  {{ doc.sync_status }}
                </span>
              </td>
              <td class="px-4 py-3 text-gray-500">{{ fmtDate(doc.created_at) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex justify-end gap-2">
                  <button @click="resync(doc)"
                          class="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition">
                    Re-sync
                  </button>
                  <button @click="confirmDelete(doc)"
                          class="text-xs px-2.5 py-1 rounded border border-red-100 text-red-500 hover:bg-red-50 transition">
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between pt-4">
        <span class="text-sm text-gray-500">{{ count }} document(s)</span>
        <div class="flex gap-2">
          <button :disabled="!prev" @click="goPage(page-1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Prev</button>
          <span class="px-3 py-1.5 text-sm text-gray-600">{{ page }}</span>
          <button :disabled="!next" @click="goPage(page+1)"
                  class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40">Next</button>
        </div>
      </div>
    </template>

    <!-- Delete confirmation modal -->
    <div v-if="deleteTarget" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
        <h3 class="font-semibold text-gray-900 mb-2">Delete Document</h3>
        <p class="text-sm text-gray-600 mb-4">
          Delete <strong>{{ deleteTarget.original_name }}</strong> from the knowledge base?
          This also removes the file from disk.
        </p>
        <div class="flex justify-end gap-3">
          <button @click="deleteTarget = null" class="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-700">Cancel</button>
          <button @click="doDelete" class="px-4 py-2 text-sm text-white rounded-lg bg-red-500 hover:bg-red-600 transition">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getKnowledge, uploadKnowledge, deleteKnowledge, resyncKnowledge } from '@/api/knowledge'
import { useUiStore } from '@/stores/ui'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const uiStore = useUiStore()
const docs    = ref([])
const loading = ref(true)
const count   = ref(0)
const next    = ref(null)
const prev    = ref(null)
const page    = ref(1)
const filters = ref({ status: '', search: '' })
const uploading      = ref(false)
const uploadingCount = ref(0)
const uploadResults  = ref([])
const deleteTarget   = ref(null)
let debounceTimer = null

async function load() {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.search) params.search = filters.value.search
    const res   = (await getKnowledge(params)).data
    docs.value  = res.results || res
    count.value = res.count ?? docs.value.length
    next.value  = res.next
    prev.value  = res.previous
  } finally { loading.value = false }
}

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 400)
}

async function onFileSelect(e) {
  const files = Array.from(e.target.files)
  if (!files.length) return
  uploading.value      = true
  uploadingCount.value = files.length
  uploadResults.value  = []
  const formData = new FormData()
  files.forEach(f => formData.append('file', f))
  try {
    const res = (await uploadKnowledge(formData)).data
    uploadResults.value = res.results || []
    uiStore.addToast(`Upload complete: ${files.length} file(s)`, 'success')
    load()
  } catch (err) {
    uiStore.addToast('Upload failed.', 'error')
  } finally {
    uploading.value = false
    e.target.value  = ''
  }
}

async function resync(doc) {
  try {
    await resyncKnowledge(doc.id)
    uiStore.addToast(`Re-sync queued for ${doc.original_name}`, 'success')
    load()
  } catch { uiStore.addToast('Re-sync failed.', 'error') }
}

function confirmDelete(doc) { deleteTarget.value = doc }

async function doDelete() {
  const doc = deleteTarget.value
  deleteTarget.value = null
  try {
    await deleteKnowledge(doc.id)
    uiStore.addToast(`Deleted ${doc.original_name}`, 'success')
    load()
  } catch { uiStore.addToast('Delete failed.', 'error') }
}

function goPage(p) { page.value = p; load() }
function fmtDate(s) { return s ? new Date(s).toLocaleDateString() : '—' }
function statusClass(s) {
  return {
    indexed:    'bg-green-100 text-green-700',
    pending:    'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-700',
    failed:     'bg-red-100 text-red-700',
  }[s] || 'bg-gray-100 text-gray-600'
}

onMounted(load)
</script>
