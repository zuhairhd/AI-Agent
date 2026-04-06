<template>
  <header class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
    <div class="text-sm text-gray-500">
      <span class="font-semibold text-gray-800">Future Smart Support</span>
      <span class="mx-2 text-gray-300">|</span>
      Admin Portal
    </div>
    <div class="flex items-center gap-4">
      <span class="text-sm text-gray-600">{{ authStore.user?.username }}</span>
      <button
        @click="handleLogout"
        class="text-sm px-3 py-1.5 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
      >Logout</button>
    </div>
  </header>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router    = useRouter()

async function handleLogout() {
  await authStore.logout()
  router.push('/portal/login')
}
</script>
