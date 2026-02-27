import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import { STORES, dbCleanExpired } from './utils/db'

// 启动时清理超过 7 天的 PDF 缓存
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
dbCleanExpired(STORES.PDFS, SEVEN_DAYS_MS).catch(e => console.warn('Cache cleanup failed:', e))

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.mount('#app')
