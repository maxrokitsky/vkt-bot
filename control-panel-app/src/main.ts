import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import './hey-api' // Initialize API client configuration

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin)

// Auth state is resolved by the router guard before the first route renders.
app.mount('#app')
