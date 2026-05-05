import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './assets/main.css'

import HomeView from './views/HomeView.vue'
import BeachView from './views/BeachView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/beach/:code', name: 'beach', component: BeachView, props: true },
  ],
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
