import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LandingPage from '@/pages/LandingPage.vue'

const routes = [
  {
    path: '/',
    name: 'landing',
    component: LandingPage,
    meta: { public: true },
  },
  {
    path: '/portal/login',
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/portal',
    component: () => import('@/components/layout/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/portal/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/pages/DashboardPage.vue') },
      { path: 'calls', name: 'Calls', component: () => import('@/pages/CallsPage.vue') },
      { path: 'calls/:id', name: 'CallDetail', component: () => import('@/pages/CallDetailPage.vue') },
      { path: 'alerts', name: 'Alerts', component: () => import('@/pages/AlertsPage.vue') },
      { path: 'followups', name: 'FollowUps', component: () => import('@/pages/FollowUpsPage.vue') },
      { path: 'knowledge', name: 'Knowledge', component: () => import('@/pages/RAGPage.vue') },
      { path: 'prompts', name: 'Prompts', component: () => import('@/pages/PromptsPage.vue') },
      { path: 'reports', name: 'Reports', component: () => import('@/pages/ReportsPage.vue') },
      { path: 'settings', name: 'Settings', component: () => import('@/pages/SettingsPage.vue') },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.clearAuth?.()
    }
  }

  if (to.meta.public) {
    return true
  }

  if (to.meta.requiresAuth && !auth.user) {
    return `/portal/login?redirect=${encodeURIComponent(to.fullPath)}`
  }

  return true
})

export default router