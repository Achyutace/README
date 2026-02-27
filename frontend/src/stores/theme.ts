/*
----------------------------------------------------------------------
                          主题store定义
----------------------------------------------------------------------
*/
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// 定义了一个叫 'theme' 的 store，负责管理应用的主题设置（深色模式/浅色模式）
export const useThemeStore = defineStore('theme', () => {
  // 从本地加载主题，如果没有则检测系统偏好，兜底浅色模式
  const getInitialTheme = () => {
    const saved = localStorage.getItem('theme')
    if (saved) return saved === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  const isDarkMode = ref(getInitialTheme())

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
