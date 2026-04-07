<template>
  <header
    class="sticky top-0 z-30 flex h-16 items-center justify-between px-6 backdrop-blur-xl border-b border-white/10"
    style="background: rgba(7,20,38,.85);"
  >
    <!-- LEFT: Page title -->
    <div class="flex items-center gap-2 text-sm">
      <span class="text-slate-400">Portal</span>
      <span class="text-slate-600">/</span>
      <span class="font-semibold text-white tracking-wide">{{ pageTitle }}</span>
    </div>

    <!-- RIGHT: Controls -->
    <div class="flex items-center gap-4">
      
      <!-- Notification bell -->
      <button
        class="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 transition-all duration-200 hover:bg-white/10 hover:text-white hover:scale-[1.05]"
        title="Notifications"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        <!-- Animated notification dot -->
        <span class="absolute right-1.5 top-1.5 flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#C49266] opacity-75"></span>
          <span class="relative inline-flex h-2 w-2 rounded-full bg-[#C49266] ring-2 ring-[#071426]"></span>
        </span>
      </button>

      <!-- Divider -->
      <div class="h-6 w-px bg-white/10"></div>

      <!-- User dropdown -->
      <div class="relative" ref="dropdownRef">
        <button
          @click="open = !open"
          class="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm transition-all duration-200 hover:bg-white/10 hover:scale-[1.02]"
        >
          <!-- Avatar -->
          <span
            class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white shadow-md"
            style="background: linear-gradient(135deg, #c49266, #d7a476);"
          >
            {{ initials }}
          </span>

          <span class="max-w-[120px] truncate font-medium text-slate-200">
            {{ authStore.user?.username }}
          </span>

          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-3.5 w-3.5 text-slate-400 transition-transform duration-200"
            :class="open ? 'rotate-180' : ''"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Dropdown -->
        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 scale-95 -translate-y-1"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 -translate-y-1"
        >
          <div
            v-if="open"
            class="absolute right-0 top-full mt-3 w-52 origin-top-right overflow-hidden rounded-2xl border border-white/10 shadow-[0_25px_60px_rgba(0,0,0,.5)]"
            style="background: rgba(10,24,45,.96); backdrop-filter: blur(18px);"
          >
            <div class="border-b border-white/10 px-4 py-3">
              <div class="text-sm font-semibold text-white">
                {{ authStore.user?.username }}
              </div>
              <div class="mt-0.5 text-xs text-slate-400">
                Administrator
              </div>
            </div>

            <div class="py-1">
              <button
                @click="handleLogout"
                class="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-red-400 transition-colors hover:bg-white/5 hover:text-red-300"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign out
              </button>
            </div>
          </div>
        </Transition>
      </div>

    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router    = useRouter()
const route     = useRoute()

const open = ref(false)
const dropdownRef = ref(null)

const initials = computed(() => {
  const name = authStore.user?.username || ''
  return name.slice(0, 2).toUpperCase() || 'A'
})

const PAGE_TITLES = {
  '/portal/dashboard':  'Dashboard',
  '/portal/calls':      'Calls',
  '/portal/alerts':     'Alerts',
  '/portal/followups':  'Follow-ups',
  '/portal/knowledge':  'Knowledge Base',
  '/portal/prompts':    'Call Prompts',
  '/portal/reports':    'Reports',
  '/portal/settings':   'Settings',
}

const pageTitle = computed(() => {
  for (const [prefix, title] of Object.entries(PAGE_TITLES)) {
    if (route.path.startsWith(prefix)) return title
  }
  return 'Admin Portal'
})

async function handleLogout() {
  open.value = false
  await authStore.logout()
  router.push('/portal/login')
}

function onClickOutside(e) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', onClickOutside))
</script>