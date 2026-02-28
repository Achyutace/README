import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../layouts/userLogin.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../layouts/userRegister.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('../layouts/LibraryLayout.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  // 首次访问时检查登录状态
  if (!authStore.authChecked) {
    await authStore.checkAuth()
  }

  // 需要登录但未登录 → 跳转登录页
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return { name: 'login' }
  }

  // 已登录但访问 guest 页面（登录/注册） → 跳转首页
  if (to.meta.guest && authStore.isLoggedIn) {
    return { name: 'home' }
  }
})

export default router
