/*
----------------------------------------------------------------------
                          主题store定义
----------------------------------------------------------------------
*/ 
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// 定义了一个叫 'theme' 的 store，负责管理应用的主题设置（深色模式/浅色模式）
export const useThemeStore = defineStore('theme', () => {
  // 从浏览器（本地）加载主题设置，如果没有则默认的浅色模式
  const isDarkMode = ref(localStorage.getItem('theme') === 'dark')

  // 监听主题变化
  watch(isDarkMode, (dark) => {
    // 更新本地主题设置
    localStorage.setItem('theme', dark ? 'dark' : 'light')

    // 更新 HTML 根元素的类，以应用相应的主题样式
    if (dark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, { immediate: true })

  // 切换主题模式（深色/浅色）
  function toggleTheme() {
    isDarkMode.value = !isDarkMode.value
  }

  // 设置指定的主题模式
  function setTheme(dark: boolean) {
    isDarkMode.value = dark
  }

  return {
    isDarkMode,
    toggleTheme,
    setTheme
  }
})
