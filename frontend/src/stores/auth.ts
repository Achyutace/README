import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, getCurrentUser, clearTokens, setCurrentUser } from '../api'

export const useAuthStore = defineStore('auth', () => {
  // ==================== 状态 ====================
  const user = ref<{ id: string; username: string; email: string } | null>(null)
  const authChecked = ref(false)
  const showLoginModal = ref(false)
  const showRegisterModal = ref(false)

  const isLoggedIn = computed(() => !!user.value)

  // ==================== 方法 ====================

  /** 启动时调用：检查当前登录状态 */
  async function checkAuth() {
    try {
      const me = await authApi.getMe()
      user.value = me
      setCurrentUser(me)
    } catch {
      user.value = null
      showLoginModal.value = true
    } finally {
      authChecked.value = true
    }
  }

  /** 登录成功回调 */
  function onLoginSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    showLoginModal.value = false
    showRegisterModal.value = false
  }

  /** 注册成功回调 */
  function onRegisterSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    showLoginModal.value = false
    showRegisterModal.value = false
  }

  /** 切换到注册弹窗 */
  function switchToRegister() {
    showLoginModal.value = false
    showRegisterModal.value = true
  }

  /** 切换到登录弹窗 */
  function switchToLogin() {
    showRegisterModal.value = false
    showLoginModal.value = true
  }

  /** auth:logout 事件处理：清空状态，弹出登录 */
  function handleLogout() {
    user.value = null
    showLoginModal.value = true
    showRegisterModal.value = false
  }

  // 监听 axios 拦截器触发的 auth:logout 事件
  window.addEventListener('auth:logout', handleLogout)

  return {
    user,
    authChecked,
    showLoginModal,
    showRegisterModal,
    isLoggedIn,
    checkAuth,
    onLoginSuccess,
    onRegisterSuccess,
    switchToRegister,
    switchToLogin,
    handleLogout,
  }
})
