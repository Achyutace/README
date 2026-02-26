<template>
    <div 
      class="fixed inset-0 z-50 flex items-center justify-center bg-blue-500/40"
    >
      <div class="w-96 bg-white dark:bg-[#252526] border border-gray-200 dark:border-[#3e3e42] rounded-lg shadow-xl overflow-hidden flex flex-col transform transition-all duration-300">
        
        <div class="px-6 py-4 bg-gray-50 dark:bg-[#2d2d30] border-b border-gray-200 dark:border-[#3e3e42] flex justify-between items-center">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            用户登录
          </h3>
          <button @click="closeModal" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors duration-200">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
  
        <div class="p-6 flex flex-col gap-4">
          
          <div>
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">邮箱</label>
            <input
              v-model="form.email"
              type="email"
              placeholder="请输入邮箱"
              class="w-full px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200"
            />
          </div>
  
          <div>
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">密码</label>
            <input 
              v-model="form.password" 
              type="password" 
              placeholder="请输入密码"
              class="w-full px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200" 
            />
          </div>
  
          <div class="flex justify-between items-center mt-1">
            <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
              <input 
                v-model="form.remember" 
                type="checkbox" 
                class="w-4 h-4 accent-sky-500 bg-white dark:bg-[#3e3e42] border-gray-200 dark:border-[#3e3e42] rounded cursor-pointer" 
              />
              记住我
            </label>
            <a href="#" class="text-sm text-sky-500 hover:text-sky-600 dark:text-sky-400 hover:underline transition-colors duration-200">
              忘记密码
            </a>
          </div>
  
          <p v-if="errorMsg" class="text-sm text-red-500">{{ errorMsg }}</p>

          <div class="flex justify-between items-end mt-4">
            <button
              @click="handleLogin"
              :disabled="loading"
              class="px-6 py-2 bg-sky-500 hover:bg-sky-600 dark:bg-[#0e639c] dark:hover:bg-[#1177bb] text-white text-sm font-medium rounded transition-colors duration-200 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ loading ? '登录中...' : '登录' }}
            </button>
            
            <div class="text-sm text-gray-600 dark:text-gray-400">
              没有账号？
              <button @click="emit('switch-to-register')" class="text-sky-500 hover:text-sky-600 dark:text-sky-400 hover:underline font-medium transition-colors duration-200 focus:outline-none">
                注册
              </button>
            </div>
          </div>
  
        </div>
      </div>
    </div>
  </template>
  
  <script setup lang="ts">
  import { reactive, ref } from 'vue'
  import { authApi } from '../../api'

  const props = defineProps({
    visible: {
      type: Boolean,
      default: false
    }
  })

  const emit = defineEmits(['update:visible', 'login-success', 'switch-to-register'])

  const form = reactive({
    email: '',
    password: '',
    remember: false
  })

  const loading = ref(false)
  const errorMsg = ref('')

  const closeModal = () => {
    emit('update:visible', false)
  }

  const handleLogin = async () => {
    errorMsg.value = ''

    if (!form.email || !form.password) {
      errorMsg.value = '请输入邮箱和密码'
      return
    }

    loading.value = true
    try {
      const res = await authApi.login(form.email, form.password)
      closeModal()
      emit('login-success', res.user)
    } catch (e: any) {
      const code = e.response?.data?.error?.code
      if (code === 'INVALID_CREDENTIALS') {
        errorMsg.value = '邮箱或密码错误'
      } else {
        errorMsg.value = e.response?.data?.error?.message || '登录失败，请稍后重试'
      }
    } finally {
      loading.value = false
    }
  }
  </script>