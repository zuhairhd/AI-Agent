<template>
  <div class="max-w-xl">
    <h1 class="text-xl font-bold text-gray-900 mb-6">Settings</h1>

    <!-- Notification Preferences -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4">
      <h2 class="text-sm font-semibold text-gray-700 mb-4">Email Notification Preferences</h2>

      <LoadingSpinner v-if="loading" />

      <template v-else>
        <div class="flex items-center justify-between mb-4">
          <label class="text-sm text-gray-700">Email Notifications Enabled</label>
          <input type="checkbox" v-model="prefs.email_enabled" class="w-4 h-4" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-1">Notification Email (override)</label>
          <input v-model="prefs.notify_email" type="email" placeholder="team@example.com"
                 class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          <p class="text-xs text-gray-400 mt-1">Leave blank to use your account email.</p>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">Alert Types (leave empty = all)</label>
          <div class="space-y-2">
            <label v-for="t in alertTypes" :key="t.value" class="flex items-center gap-2 text-sm">
              <input type="checkbox" :value="t.value"
                     v-model="prefs.notify_on" class="w-4 h-4" />
              {{ t.label }}
            </label>
          </div>
        </div>

        <button @click="save"
                class="px-4 py-2 text-sm text-white rounded-lg"
                style="background: var(--fss-bronze)">Save Preferences</button>

        <div v-if="saved" class="mt-3 text-sm text-green-600">Preferences saved.</div>
      </template>
    </div>

    <!-- Branding info -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <h2 class="text-sm font-semibold text-gray-700 mb-3">Branding</h2>
      <p class="text-sm text-gray-500">Future Smart Support Admin Portal</p>
      <p class="text-xs text-gray-400 mt-1">For logo and company name changes, contact your system administrator.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const prefs   = ref({ email_enabled: true, notify_email: '', notify_on: [] })
const loading = ref(true)
const saved   = ref(false)

const alertTypes = [
  { value: 'low_confidence',   label: 'Low AI Confidence' },
  { value: 'no_answer',        label: 'No Answer Found' },
  { value: 'human_requested',  label: 'Human Agent Requested' },
  { value: 'dropped_call',     label: 'Call Dropped' },
  { value: 'repeated_failure', label: 'Repeated Failed Interaction' },
  { value: 'unresolved',       label: 'Call Unresolved' },
]

onMounted(async () => {
  try { prefs.value = (await api.get('/api/portal/settings/notifications/')).data }
  finally { loading.value = false }
})

async function save() {
  await api.put('/api/portal/settings/notifications/', prefs.value)
  saved.value = true
  setTimeout(() => { saved.value = false }, 3000)
}
</script>
