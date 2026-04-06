<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-gray-900">Reports</h1>
      <div class="flex gap-2">
        <button v-for="p in periods" :key="p.value"
                @click="period = p.value; load()"
                class="px-3 py-1.5 text-sm rounded-lg border transition-colors"
                :class="period === p.value
                  ? 'text-white border-transparent'
                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
                :style="period === p.value ? 'background: var(--fss-bronze)' : ''">
          {{ p.label }}
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <!-- Summary KPIs -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard label="Total Calls"      :value="data?.total"      icon="📞" />
        <KpiCard label="Resolved"         :value="data?.resolved"   icon="✅" />
        <KpiCard label="Unresolved"       :value="data?.unresolved" icon="⚠️" />
        <KpiCard label="Escalated"        :value="data?.escalated"  icon="🔺" />
      </div>

      <!-- Daily Volume Table -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h2 class="text-sm font-semibold text-gray-700 mb-4">Daily Call Volume</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="text-left px-4 py-2 text-gray-600 font-semibold">Date</th>
                <th class="text-left px-4 py-2 text-gray-600 font-semibold">Calls</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in data?.daily_volume" :key="d.date" class="border-t border-gray-50">
                <td class="px-4 py-2 text-gray-700">{{ d.date }}</td>
                <td class="px-4 py-2">
                  <div class="flex items-center gap-2">
                    <div class="h-2 rounded-full" style="background: var(--fss-bronze)"
                         :style="{ width: `${Math.min((d.count / maxCount) * 200, 200)}px` }"></div>
                    <span class="text-gray-700">{{ d.count }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getReports } from '@/api/reports'
import KpiCard from '@/components/ui/KpiCard.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const data    = ref(null)
const loading = ref(true)
const period  = ref('30d')
const periods = [{ value:'7d', label:'7 days' }, { value:'30d', label:'30 days' }, { value:'90d', label:'90 days' }]

const maxCount = computed(() => Math.max(...(data.value?.daily_volume?.map(d => d.count) || [1]), 1))

async function load() {
  loading.value = true
  try { data.value = (await getReports(period.value)).data }
  finally { loading.value = false }
}

onMounted(load)
</script>
