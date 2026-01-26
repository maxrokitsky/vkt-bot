import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { getCurrentUserInfoApiAuthMeGet } from './client'
import './hey-api' // Initialize API client configuration

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin)

// Initialize auth state from token
const authStore = useAuthStore()
if (authStore.isAuthenticated) {
  getCurrentUserInfoApiAuthMeGet()
    .then((response) => {
      if (response.data) {
        authStore.setUser(response.data)
      }
    })
    .catch(() => {
      authStore.logout()
    })
}

app.mount('#app')
