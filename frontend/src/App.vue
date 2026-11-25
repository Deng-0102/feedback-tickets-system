<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const showHeader = computed(() => route.name !== 'login')

function signOut() {
  auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header v-if="showHeader" class="app-header">
      <RouterLink class="brand" :to="auth.homePath">智能反馈工单系统</RouterLink>
      <div v-if="auth.user" class="user-actions">
        <span>{{ auth.user.display_name }} · {{ auth.roleLabel }}</span>
        <button class="button button-secondary" type="button" @click="signOut">退出登录</button>
      </div>
    </header>
    <main :class="{ 'page-container': showHeader }">
      <RouterView />
    </main>
  </div>
</template>
