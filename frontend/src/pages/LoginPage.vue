<template>
  <div class="relative min-h-screen overflow-hidden bg-[#071426] text-white">
    <!-- Background image -->
    <div
      class="absolute inset-0 opacity-20 pointer-events-none"
      :style="{
        backgroundImage: `url(${coverImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }"
    ></div>

    <!-- Background overlays -->
    <div
      class="absolute inset-0 pointer-events-none"
      style="background:
        radial-gradient(circle at 20% 25%, rgba(196,146,102,.18), transparent 30%),
        radial-gradient(circle at 80% 20%, rgba(42,212,255,.10), transparent 28%),
        linear-gradient(180deg, rgba(7,20,38,.90), rgba(7,20,38,.96));"
    ></div>

    <div class="relative z-10 min-h-screen flex items-center justify-center px-6 py-10">
      <div class="w-full max-w-md">
        <!-- Brand -->
        <div class="text-center mb-8">
          <div class="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md">
            <img :src="logo" alt="Future Smart Support" class="h-14 w-14 object-contain" />
          </div>
          <h1 class="text-4xl font-bold text-white tracking-tight">Future Smart Support</h1>
          <p class="text-slate-300 text-sm mt-2">AI Admin Portal</p>
        </div>

        <!-- Login box -->
        <div class="relative">
          <div
            class="absolute inset-0 rounded-3xl blur-2xl opacity-30"
            style="background: radial-gradient(circle, rgba(196,146,102,.35), transparent 60%)"
          ></div>

          <div
            class="relative rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,255,255,0.92))] p-8 shadow-[0_25px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl"
          >
            <h2 class="text-2xl font-bold text-gray-800 mb-2">Sign in to your account</h2>
            <p class="text-sm text-gray-500 mb-6">Access the Future Smart Support admin portal.</p>

            <form @submit.prevent="handleLogin" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Username or Email</label>
                <input
                  v-model="form.username"
                  type="text"
                  required
                  placeholder="admin"
                  class="w-full px-4 py-3 rounded-xl text-sm bg-white border border-gray-200 text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#c49266] focus:border-transparent"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input
                  v-model="form.password"
                  type="password"
                  required
                  placeholder="••••••••"
                  class="w-full px-4 py-3 rounded-xl text-sm bg-white border border-gray-200 text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#c49266] focus:border-transparent"
                />
              </div>

              <div
                v-if="error"
                class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {{ error }}
              </div>

              <button
                type="submit"
                :disabled="loading"
                class="w-full py-3 rounded-xl text-sm font-semibold text-white shadow-[0_10px_24px_rgba(196,146,102,0.28)] transition-all duration-200"
                :class="loading ? 'opacity-60 cursor-not-allowed' : 'hover:scale-[1.02] active:scale-[0.98]'"
                style="background: linear-gradient(135deg, #c49266, #d7a476)"
              >
                {{ loading ? 'Signing in…' : 'Sign In' }}
              </button>
            </form>

            <div class="mt-8 border-t border-gray-200 pt-6 text-center text-sm text-gray-500">
              <div class="font-medium text-gray-700">Future Smart Support</div>
              <div class="mt-2">majid@FutureSmartSupport.com</div>
              <div>GSM: 92771730</div>
              <div class="mt-1">futuresmartsupport.com</div>
            </div>
          </div>
        </div>

        <p class="text-center text-xs text-slate-500 mt-6">
          © {{ new Date().getFullYear() }} Future Smart Support
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import logo from '@/assets/branding/FSS_Logo.svg'
import coverImage from '@/assets/branding/cover_image.png'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
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