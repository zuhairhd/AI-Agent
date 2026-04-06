<template>
  <div class="flex h-screen overflow-hidden bg-gray-100">
    <AppSidebar />
    <div class="flex flex-col flex-1 overflow-hidden">
      <AppTopbar />
      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
    <!-- Toast notifications -->
    <div class="fixed bottom-4 right-4 z-50 space-y-2">
      <transition-group name="toast">
        <div
          v-for="toast in uiStore.toasts"
          :key="toast.id"
          class="px-4 py-3 rounded-lg shadow-lg text-white text-sm font-medium"
          :class="{
            'bg-green-600': toast.type === 'success',
            'bg-red-600':   toast.type === 'error',
            'bg-blue-600':  toast.type === 'info',
          }"
        >{{ toast.message }}</div>
      </transition-group>
    </div>
  </div>
</template>

<script setup>
import { useUiStore } from '@/stores/ui'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
const uiStore = useUiStore()
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all .3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
