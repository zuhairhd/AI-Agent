<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b border-gray-100">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="text-left px-4 py-3 font-semibold text-gray-600 whitespace-nowrap"
            >{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length" class="py-12 text-center text-gray-400">Loading…</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td :colspan="columns.length" class="py-12 text-center text-gray-400">No records found.</td>
          </tr>
          <tr
            v-else
            v-for="(row, i) in rows"
            :key="i"
            class="border-b border-gray-50 last:border-0 transition-colors"
            :class="clickable ? 'hover:bg-gray-50 cursor-pointer' : ''"
            @click="clickable && $emit('row-click', row)"
          >
            <td v-for="col in columns" :key="col.key" class="px-4 py-3">
              <slot :name="col.key" :row="row" :value="row[col.key]">
                {{ row[col.key] ?? '—' }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="count !== undefined" class="px-4 py-3 flex items-center justify-between border-t border-gray-100">
      <span class="text-sm text-gray-500">{{ count }} total</span>
      <div class="flex gap-2">
        <button
          :disabled="!hasPrev"
          @click="$emit('page', currentPage - 1)"
          class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40"
        >Prev</button>
        <span class="px-3 py-1.5 text-sm text-gray-600">{{ currentPage }}</span>
        <button
          :disabled="!hasNext"
          @click="$emit('page', currentPage + 1)"
          class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40"
        >Next</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  columns:     { type: Array,   required: true },
  rows:        { type: Array,   default: () => [] },
  loading:     { type: Boolean, default: false },
  clickable:   { type: Boolean, default: false },
  count:       Number,
  currentPage: { type: Number, default: 1 },
  hasNext:     Boolean,
  hasPrev:     Boolean,
})
defineEmits(['row-click', 'page'])
</script>
