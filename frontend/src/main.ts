import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import { initMockAuth } from './api'

// 在应用挂载前，先尝试初始化一个 Mock Token
// TODO 
initMockAuth()

// 利用 App.vue 里面的组件创建 Vue 应用实例 app
const app = createApp(App)

// 创建 Pinia 状态管理实例 pinia
const pinia = createPinia()

// 将 Pinia 插件安装到 Vue 应用中
app.use(pinia)

// 将 Vue 应用挂载到 index.html 中 id="app" 的元素上
// 这步的目的是将文字状的 HTML 形式化成一个内存中
// 这样可以渲染为文字的组件，从而实现页面的动态交互
app.mount('#app')
