import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(true)
  const toasts = ref([])

  function toggleSidebar() { sidebarOpen.value = !sidebarOpen.value }

  function addToast(message, type = 'info', duration = 4000) {
    const id = Date.now()
    toasts.value.push({ id, message, type })
    setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, duration)
  }

  return { sidebarOpen, toasts, toggleSidebar, addToast }
})
