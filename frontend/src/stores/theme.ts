import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // Load theme from localStorage or default to light
  const isDarkMode = ref(localStorage.getItem('theme') === 'dark')

  // Watch for changes and update localStorage and document class
  watch(isDarkMode, (dark) => {
    localStorage.setItem('theme', dark ? 'dark' : 'light')
    if (dark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, { immediate: true })

  function toggleTheme() {
    isDarkMode.value = !isDarkMode.value
  }

  function setTheme(dark: boolean) {
    isDarkMode.value = dark
  }

  return {
    isDarkMode,
    toggleTheme,
    setTheme
  }
})
