<template>
  <aside class="flex w-72 min-h-screen flex-col border-r border-white/10 bg-[linear-gradient(180deg,#071426_0%,#0b1932_100%)] text-white shadow-2xl">
    <!-- Brand -->
    <div class="border-b border-white/10 px-5 py-5">
      <div class="flex items-center gap-3">
        <div class="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 shadow-lg backdrop-blur-md">
          <img :src="logo" alt="Future Smart Support" class="h-10 w-10 object-contain" />
        </div>
        <div class="min-w-0">
          <div class="truncate text-base font-bold leading-tight text-white">Future Smart Support</div>
          <div class="mt-1 text-xs tracking-[0.16em] text-slate-400 uppercase">AI Admin Portal</div>
        </div>
      </div>

      <div class="mt-4 rounded-2xl border border-[rgba(196,146,102,.16)] bg-[rgba(255,255,255,.04)] p-4">
        <div class="text-xs uppercase tracking-[0.14em] text-slate-400">System Status</div>
        <div class="mt-2 flex items-center gap-2">
          <span class="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.8)]"></span>
          <span class="text-sm font-medium text-slate-200">Online and Ready</span>
        </div>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-5">
      <div class="mb-3 px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        Navigation
      </div>

      <div class="space-y-1.5">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="group flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200"
          :class="isActive(item.to)
            ? 'text-white shadow-lg'
            : 'text-slate-400 hover:text-white hover:bg-white/5'"
          :style="isActive(item.to)
            ? 'background: linear-gradient(135deg, rgba(196,146,102,.20), rgba(196,146,102,.10)); border: 1px solid rgba(196,146,102,.20);'
            : ''"
        >
          <span
            class="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-base transition-all duration-200"
            :style="isActive(item.to)
              ? 'color: var(--fss-bronze); background: rgba(196,146,102,.12); border-color: rgba(196,146,102,.16);'
              : ''"
          >
            {{ item.icon }}
          </span>

          <span class="truncate">{{ item.label }}</span>

          <span
            v-if="item.badge"
            class="ml-auto rounded-full bg-red-500/90 px-2 py-0.5 text-[11px] font-semibold text-white"
          >
            {{ item.badge }}
          </span>
        </router-link>
      </div>
    </nav>

    <!-- Contact block -->
    <div class="mx-4 mb-4 rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
      <div class="text-xs uppercase tracking-[0.14em] text-slate-500">Contact</div>
      <div class="mt-3 space-y-2 text-sm text-slate-300">
        <div class="truncate">majid@FutureSmartSupport.com</div>
        <div>GSM: 92771730</div>
        <div class="truncate">futuresmartsupport.com</div>
      </div>
    </div>

    <!-- Footer -->
    <div class="border-t border-white/10 px-5 py-4 text-xs text-slate-500">
      <div class="font-medium text-slate-400">Future Smart Support</div>
      <div class="mt-1">v1.0 • FSS Admin Portal</div>
    </div>
  </aside>
</template>

<script setup>
import { useRoute } from 'vue-router'
import logo from '@/assets/branding/FSS_Logo.svg'

const route = useRoute()

const navItems = [
  { label: 'Dashboard', to: '/portal/dashboard', icon: '📊' },
  { label: 'Calls', to: '/portal/calls', icon: '📞' },
  { label: 'Alerts', to: '/portal/alerts', icon: '🔔' },
  { label: 'Follow-ups', to: '/portal/followups', icon: '📋' },
  { label: 'Knowledge Base', to: '/portal/knowledge', icon: '📚' },
  { label: 'Prompts', to: '/portal/prompts', icon: '🎙️' },
  { label: 'Reports', to: '/portal/reports', icon: '📈' },
  { label: 'Settings', to: '/portal/settings', icon: '⚙️' },
]

const isActive = (to) => route.path.startsWith(to)
</script>