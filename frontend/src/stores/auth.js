import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)

  async function login(username, password) {
    const res = await api.post('/api/portal/auth/login/', { username, password })
    user.value = res.data
  }

  async function logout() {
    await api.post('/api/portal/auth/logout/')
    user.value = null
  }

  async function fetchMe() {
    const res = await api.get('/api/portal/auth/me/')
    user.value = res.data
  }

  return { user, login, logout, fetchMe }
})
