import axios from 'axios'

const TOKEN_KEY = 'feedback_ticket_token'
let onUnauthorized: (() => void) | undefined

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token && config.url !== '/auth/login') {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (
      error.response?.status === 401 &&
      token &&
      error.config?.headers.get('Authorization') === `Bearer ${token}`
    ) {
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)
