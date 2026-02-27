import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, setCurrentUser, getCurrentUser, getAccessToken, getRefreshToken, clearTokens, setTokens } from '../api'
import router from '../router'
import { useLibraryStore } from './library'
import { useChatStore } from './chat'
import { useRoadmapStore } from './roadmap'
import { useTranslationStore } from './translation'
import { broadcastSync, syncChannel } from '../utils/broadcast'
import type { SyncMessage } from '../utils/broadcast'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  // ==================== 状态 ====================
  const user = ref<{ id: string; username: string; email: string } | null>(null)
  const authChecked = ref(false)

  const isLoggedIn = computed(() => !!user.value)

  // ==================== 方法 ====================

  /**
   * 启动时调用：检查当前登录状态
   *
   * 策略：
   * 1. 本地无任何 Token → 直接判定未登录
   * 2. 本地有缓存用户信息 → 立即水合 Pinia（路由不阻塞）
   * 3. 后台静默调用 GET /auth/me 验证 accessToken。
   *    - 成功 → 更新用户信息。
   *    - 失败(401) → 检查 refreshToken 是否仍有效：
   *        * refreshToken 有效 → 换取新 accessToken，再次水合。
   *        * refreshToken 已失效 → 静默清空状态，跳转登录页。
   *    - 其他网络错误 → 保留本地缓存状态（离线容错）。
   */
  async function checkAuth() {
    // Step 1：本地无 Token，直接判断为未登录
    if (!getAccessToken() && !getRefreshToken()) {
      user.value = null
      authChecked.value = true
      return
    }

    // Step 2：读取本地缓存的用户信息，立即水合（让路由守卫不必等待网络）
    const cachedUser = getCurrentUser()
    if (cachedUser) {
      user.value = cachedUser
    }
    // 本轮 authChecked 先设为 true，路由守卫不再阻塞
    authChecked.value = true

    // Step 3：后台静默验证（不 await，不阻塞路由）
    _silentValidate()
  }

  /**
   * 后台静默身份验证
   *
   * 注意：此函数故意不被 await，后台运行。
   * 若 accessToken 过期，尝试用 refreshToken 续签。
   * 若 refreshToken 也失效，执行静默登出（清空状态 + 跳转登录页）。
   */
  async function _silentValidate() {
    try {
      // 尝试用当前 accessToken 获取用户信息
      const me = await authApi.getMe()
      user.value = me
      setCurrentUser(me)
    } catch (err: any) {
      const status = err?.response?.status

      if (status === 401) {
        // accessToken 失效，尝试用 refreshToken 换新
        const refreshToken = getRefreshToken()
        if (!refreshToken) {
          // 没有 refreshToken，直接静默登出
          _silentLogout()
          return
        }

        try {
          // 直接调用 refresh 接口，绕过 axios 拦截器（避免触发 auth:logout 事件循环）
          const { data } = await axios.post(
            `${import.meta.env.VITE_API_URL || 'http://localhost:5000/api'}/auth/refresh`,
            { refreshToken }
          )
          // 保存新 Token
          setTokens(data.accessToken, refreshToken)

          // 用新 Token 再次获取用户信息
          const me = await authApi.getMe()
          user.value = me
          setCurrentUser(me)
        } catch (refreshErr: any) {
          const refreshStatus = refreshErr?.response?.status
          if (refreshStatus === 401) {
            // refreshToken 也已失效，静默登出
            _silentLogout()
          }
          // 其他错误（网络断开等）→ 保留本地缓存，不强制登出
        }
      }
      // 状态码非 401（如 500、网络超时）→ 离线容错，保留本地缓存
    }
  }

  /**
   * 静默登出（仅用于 _silentValidate 内部）
   * 不广播跨标签页事件，不触发 auth:logout 自定义事件（避免拦截器循环）。
   */
  function _silentLogout() {
    clearTokens()
    user.value = null
    _clearAllStores()
    router.push('/login')
  }

  /** 登录成功：设置用户，跳转首页 */
  async function onLoginSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    // 登录成功后，强制刷新文献库缓存
    const libraryStore = useLibraryStore()
    await libraryStore.fetchDocuments(true)
    router.push('/')
  }

  /** 注册成功：设置用户，跳转首页 */
  async function onRegisterSuccess(userData: { id: string; username: string; email: string }) {
    user.value = userData
    // 注册成功同理
    const libraryStore = useLibraryStore()
    await libraryStore.fetchDocuments(true)
    router.push('/')
  }

  /** 清空所有业务 Store 缓存（内部复用） */
  function _clearAllStores() {
    useLibraryStore().clearLibrary()
    useChatStore().clearAllData()
    useRoadmapStore().clearAllData()
    useTranslationStore().clearCache()
  }

  /** auth:logout 事件处理：清空状态，跳转登录页 */
  function handleLogout() {
    user.value = null
    _clearAllStores()

    // 广播到其它标签页
    broadcastSync('AUTH_LOGOUT')

    router.push('/login')
  }

  // 监听跨标签页同步
  syncChannel.addEventListener('message', (event: MessageEvent<SyncMessage>) => {
    if (event.data.type === 'AUTH_LOGOUT') {
      // 其它标签页退出了，本页也执行清理
      user.value = null
      _clearAllStores()
      router.push('/login')
    }
  })

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
