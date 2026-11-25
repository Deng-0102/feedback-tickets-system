import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'
import type { LoginPayload, Role, UserProfile } from '@/types/api'

const TOKEN_KEY = 'feedback_ticket_token'
const USER_KEY = 'feedback_ticket_user'

function readStoredUser(): UserProfile | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserProfile
  } catch {
    localStorage.removeItem(USER_KEY)
    return null
  }
}

const roleHome: Record<Role, string> = {
  USER: '/user',
  AGENT: '/agent',
  ADMIN: '/admin',
}

const roleNames: Record<Role, string> = {
  USER: '普通用户',
  AGENT: '处理人员',
  ADMIN: '管理员',
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserProfile | null>(readStoredUser())
  const loading = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value && user.value))
  const homePath = computed(() => (user.value ? roleHome[user.value.role] : '/login'))
  const roleLabel = computed(() => (user.value ? roleNames[user.value.role] : ''))

  async function login(payload: LoginPayload) {
    loading.value = true
    try {
      const result = await authApi.login(payload)
      token.value = result.access_token
      user.value = result.user
      localStorage.setItem(TOKEN_KEY, result.access_token)
      localStorage.setItem(USER_KEY, JSON.stringify(result.user))
      return result.user
    } finally {
      loading.value = false
    }
  }

  async function refreshProfile() {
    if (!token.value) return null
    const profile = await authApi.me()
    user.value = profile
    localStorage.setItem(USER_KEY, JSON.stringify(profile))
    return profile
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    loading,
    isAuthenticated,
    homePath,
    roleLabel,
    login,
    refreshProfile,
    logout,
  }
})
