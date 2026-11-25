<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import type { ApiErrorData } from '@/types/api'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
})

async function submit() {
  errorMessage.value = ''
  try {
    await auth.login(form)
    const requestedRedirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const redirect = requestedRedirect.startsWith('/') && !requestedRedirect.startsWith('//')
      ? requestedRedirect
      : auth.homePath
    await router.replace(redirect)
  } catch (error) {
    if (axios.isAxiosError<ApiErrorData>(error)) {
      errorMessage.value = error.response?.data?.message ?? error.response?.data?.detail ?? '登录失败，请检查账号和密码。'
    } else {
      errorMessage.value = '登录失败，请稍后重试。'
    }
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-intro">
      <p class="eyebrow">FEEDBACK & TICKETS</p>
      <h1>让每条用户反馈<br />都有清晰的处理结果</h1>
      <p>反馈提交、智能整理、工单分配、处理跟踪和统计分析统一在一个系统中完成。</p>
    </section>

    <form class="auth-card" @submit.prevent="submit">
      <div>
        <p class="eyebrow">欢迎回来</p>
        <h2>登录系统</h2>
      </div>

      <label>
        用户名
        <input v-model.trim="form.username" autocomplete="username" required placeholder="请输入用户名" />
      </label>

      <label>
        密码
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          required
          placeholder="请输入密码"
        />
      </label>

      <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
      <button class="button button-primary button-block" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '正在登录…' : '登录' }}
      </button>
      <p class="form-hint">测试账号由项目初始化脚本创建，请勿在前端写入默认密码。</p>
    </form>
  </div>
</template>
