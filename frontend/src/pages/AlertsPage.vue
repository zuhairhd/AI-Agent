<template>
  <div>
    <h1 class="text-xl font-bold text-gray-900 mb-6">Alerts</h1>

    <FilterBar class="mb-4">
      <select v-model="filters.status" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
        <option value="">All Statuses</option>
        <option value="open">Open</option>
        <option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option>
        <option value="dismissed">Dismissed</option>
      </select>
      <select v-model="filters.severity" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
        <option value="">All Severities</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
    </FilterBar>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <EmptyState v-if="alerts.length === 0" icon="🔔" title="No alerts" message="No alerts match your filters." />

      <div v-else class="space-y-3">
        <AlertCard v-for="alert in alerts" :key="alert.id" :alert="alert">
          <template #actions>
            <router-link
              v-if="alert.session"
              :to="`/portal/calls/${alert.session}`"
              class="text-xs hover:underline"
              style="color: var(--fss-bronze)"
            >View Call</router-link>
            <button
              v-if="alert.send_email"
              @click="resend(alert.id)"
              class="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
            >Resend Email</button>
            <button
              v-if="alert.status !== 'resolved'"
              @click="resolve(alert.id)"
              class="text-xs px-2.5 py-1 rounded border border-green-200 text-green-700 hover:bg-green-50"
            >Resolve</button>
          </template>
        </AlertCard>
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
import { getAlerts, patchAlert, resendEmail } from '@/api/alerts'
import { useUiStore } from '@/stores/ui'
import AlertCard      from '@/components/ui/AlertCard.vue'
import FilterBar      from '@/components/ui/FilterBar.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import EmptyState     from '@/components/ui/EmptyState.vue'

const alerts  = ref([])
const loading = ref(true)
const count   = ref(0)
const next    = ref(null)
const prev    = ref(null)
const page    = ref(1)
const filters = ref({ status: 'open', severity: '' })
const uiStore = useUiStore()

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, ...Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v)) }
    const res    = (await getAlerts(params)).data
    alerts.value = res.results || res
    count.value  = res.count ?? alerts.value.length
    next.value   = res.next
    prev.value   = res.previous
  } finally { loading.value = false }
}

async function resend(id) {
  try { await resendEmail(id); uiStore.addToast('Resend queued.', 'success') }
  catch { uiStore.addToast('Resend failed.', 'error') }
}

async function resolve(id) {
  try {
    await patchAlert(id, { status: 'resolved' })
    uiStore.addToast('Alert resolved.', 'success')
    load()
  } catch { uiStore.addToast('Failed to resolve.', 'error') }
}

function goPage(p) { page.value = p; load() }
onMounted(load)
</script>
