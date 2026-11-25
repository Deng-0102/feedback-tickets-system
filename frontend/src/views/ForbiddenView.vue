<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <section class="status-page">
    <p class="status-code">403</p>
    <h1>没有访问权限</h1>
    <p>当前角色不能访问这个页面。如需操作，请联系管理员确认权限。</p>
    <RouterLink class="button button-primary" :to="auth.homePath">返回工作台</RouterLink>
  </section>
</template>
