import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, setCurrentUser } from '../api'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  // ==================== 状态 ====================
  const user = ref<{ id: string; username: string; email: string } | null>(null)
  const authChecked = ref(false)

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
    } finally {
      authChecked.value = true
    }
  }

  /** 登录成功：设置用户，跳转首页 */
  function onLoginSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    router.push('/')
  }

  /** 注册成功：设置用户，跳转首页 */
  function onRegisterSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    router.push('/')
  }

  /** auth:logout 事件处理：清空状态，跳转登录页 */
  function handleLogout() {
    user.value = null
    router.push('/login')
  }

  // 监听 axios 拦截器触发的 auth:logout 事件
  window.addEventListener('auth:logout', handleLogout)

  return {
    user,
    authChecked,
    isLoggedIn,
    checkAuth,
    onLoginSuccess,
    onRegisterSuccess,
    handleLogout,
  }
})
