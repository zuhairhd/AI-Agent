<template>
  <div class="min-h-screen flex items-center justify-center" style="background: var(--sidebar-bg);">
    <div class="w-full max-w-sm">
      <!-- Brand -->
      <div class="text-center mb-8">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white mx-auto mb-4"
             style="background: var(--fss-bronze)">F</div>
        <h1 class="text-2xl font-bold text-white">Future Smart Support</h1>
        <p class="text-gray-400 text-sm mt-1">Admin Portal</p>
      </div>

      <!-- Card -->
      <div class="bg-white rounded-2xl shadow-2xl p-8">
        <h2 class="text-lg font-semibold text-gray-800 mb-6">Sign in to your account</h2>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Username or Email</label>
            <input
              v-model="form.username"
              type="text"
              required
              class="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent"
              style="--tw-ring-color: var(--fss-bronze)"
              placeholder="admin"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              v-model="form.password"
              type="password"
              required
              class="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2"
              placeholder="••••••••"
            />
          </div>

          <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2.5 rounded-lg text-white font-semibold text-sm transition-opacity"
            :class="loading ? 'opacity-60 cursor-not-allowed' : 'hover:opacity-90'"
            style="background: var(--fss-bronze)"
          >{{ loading ? 'Signing in…' : 'Sign In' }}</button>
        </form>
      </div>

      <p class="text-center text-xs text-gray-500 mt-6">&copy; {{ new Date().getFullYear() }} Future Smart Support</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router    = useRouter()
const route     = useRoute()

const form    = ref({ username: '', password: '' })
const loading = ref(false)
const error   = ref('')

async function handleLogin() {
  error.value   = ''
  loading.value = true
  try {
    await authStore.login(form.value.username, form.value.password)
    const redirect = route.query.redirect || '/portal/dashboard'
    router.push(redirect)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed. Please check your credentials.'
  } finally {
    loading.value = false
  }
}
</script>
