import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types/api'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    roles?: Role[]
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/login',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/user',
      name: 'user-home',
      component: () => import('@/views/UserHomeView.vue'),
      meta: { roles: ['USER'] },
    },
    {
      path: '/agent',
      name: 'agent-home',
      component: () => import('@/views/AgentHomeView.vue'),
      meta: { roles: ['AGENT'] },
    },
    {
      path: '/admin',
      name: 'admin-home',
      component: () => import('@/views/AdminHomeView.vue'),
      meta: { roles: ['ADMIN'] },
    },
    {
      path: '/403',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { public: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true },
    },
  ],
})

let initialSession: Promise<void> | undefined

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  initialSession ??= (async () => {
    if (!auth.token) return
    try {
      await auth.refreshProfile()
    } catch {
      auth.logout()
    }
  })()
  await initialSession

  if (to.name === 'login' && auth.isAuthenticated) {
    return auth.homePath
  }

  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.roles && auth.user && !to.meta.roles.includes(auth.user.role)) {
    return { name: 'forbidden' }
  }

  return true
})

export default router
