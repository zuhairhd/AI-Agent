<template>
  <aside
    class="flex flex-col w-64 min-h-screen text-white transition-all"
    style="background: var(--sidebar-bg);"
  >
    <!-- Logo / brand -->
    <div class="flex items-center gap-3 px-6 py-5 border-b border-white/10">
      <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
           style="background: var(--fss-bronze);">F</div>
      <div>
        <div class="text-sm font-semibold text-white leading-tight">Future Smart</div>
        <div class="text-xs text-gray-400">Support Portal</div>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.name"
        :to="item.to"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
        :class="isActive(item.to)
          ? 'text-white' : 'text-gray-400 hover:text-white'"
        :style="isActive(item.to) ? 'background: var(--sidebar-active);' : ''"
        @mouseover="e => { if (!isActive(item.to)) e.currentTarget.style.background = 'var(--sidebar-hover)' }"
        @mouseleave="e => { if (!isActive(item.to)) e.currentTarget.style.background = '' }"
      >
        <span class="text-base">{{ item.icon }}</span>
        {{ item.label }}
        <span v-if="item.badge" class="ml-auto bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
          {{ item.badge }}
        </span>
      </router-link>
    </nav>

    <!-- Bottom -->
    <div class="px-4 py-4 border-t border-white/10 text-xs text-gray-500">
      v1.0 &bull; FSS Admin Portal
    </div>
  </aside>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const navItems = [
  { label: 'Dashboard',   to: '/portal/dashboard', icon: '📊' },
  { label: 'Calls',       to: '/portal/calls',     icon: '📞' },
  { label: 'Alerts',      to: '/portal/alerts',    icon: '🔔' },
  { label: 'Follow-ups',  to: '/portal/followups', icon: '📋' },
  { label: 'Reports',     to: '/portal/reports',   icon: '📈' },
  { label: 'Settings',    to: '/portal/settings',  icon: '⚙️' },
]
const isActive = (to) => route.path.startsWith(to)
</script>
