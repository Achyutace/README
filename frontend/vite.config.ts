import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      // 创建别名： @ 指向 src 目录，方便在项目中引用 src 目录下的文件
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
