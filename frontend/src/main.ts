import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import { initMockAuth } from './api'

;(async () => {
	try {
		await initMockAuth()
	} catch (err) {
		// ignore, app can still start without auth but subsequent requests may 401
		console.warn('initMockAuth failed or skipped', err)
	}

	const app = createApp(App)
	const pinia = createPinia()
	app.use(pinia)
	app.use(router)
	app.mount('#app')
})()
