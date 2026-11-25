import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { setUnauthorizedHandler } from './api/http'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles.css'

const pinia = createPinia()
const app = createApp(App).use(pinia)
const auth = useAuthStore(pinia)
setUnauthorizedHandler(() => {
  auth.logout()
  const route = router.currentRoute.value
  if (route.matched.length > 0 && !route.meta.public) {
    void router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
})
app.use(router).mount('#app')
