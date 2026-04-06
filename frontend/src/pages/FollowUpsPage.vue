<template>
  <div>
    <h1 class="text-xl font-bold text-gray-900 mb-6">Follow-ups</h1>

    <FilterBar class="mb-4">
      <select v-model="filters.status" @change="load"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="in_progress">In Progress</option>
        <option value="completed">Completed</option>
      </select>
    </FilterBar>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <EmptyState v-if="followups.length === 0" icon="📋" title="No follow-ups" message="No follow-up tasks found." />

      <div v-else class="space-y-3">
        <FollowUpCard
          v-for="fu in followups"
          :key="fu.id"
          :followup="fu"
          @complete="markComplete"
        />
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
import FollowUpCard   from '@/components/ui/FollowUpCard.vue'
import FilterBar      from '@/components/ui/FilterBar.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import EmptyState     from '@/components/ui/EmptyState.vue'

const followups = ref([])
const loading   = ref(true)
const count     = ref(0)
const next      = ref(null)
const prev      = ref(null)
const page      = ref(1)
const filters   = ref({ status: 'pending' })
const uiStore   = useUiStore()

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, ...Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v)) }
    const res    = (await getFollowUps(params)).data
    followups.value = res.results || res
    count.value     = res.count ?? followups.value.length
    next.value      = res.next
    prev.value      = res.previous
  } finally { loading.value = false }
}

async function markComplete(fu) {
  try {
    await patchFollowUp(fu.id, { status: 'completed', completed_at: new Date().toISOString() })
    uiStore.addToast('Marked as complete.', 'success')
    load()
  } catch { uiStore.addToast('Update failed.', 'error') }
}

function goPage(p) { page.value = p; load() }
onMounted(load)
</script>
