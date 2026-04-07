import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)

  async function login(username, password) {
    const res = await api.post('/api/portal/auth/login/', { username, password })
    user.value = res.data
    return res.data
  }

  async function logout() {
    try {
      await api.post('/api/portal/auth/logout/')
    } catch (error) {
      console.warn('Logout API failed, clearing local auth state anyway.', error)
    } finally {
      user.value = null
    }
  }

  async function fetchMe() {
    try {
      const res = await api.get('/api/portal/auth/me/')
      user.value = res.data
      return res.data
    } catch (error) {
      user.value = null
      throw error
    }
  }

  function clearAuth() {
    user.value = null
  }

  return { user, login, logout, fetchMe, clearAuth }
})