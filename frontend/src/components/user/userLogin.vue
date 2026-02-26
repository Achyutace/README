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
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">手机号</label>
            <input 
              v-model="form.phone" 
              type="tel" 
              placeholder="请输入手机号"
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
  
          <div class="flex justify-between items-end mt-4">
            <button 
              @click="handleLogin"
              class="px-6 py-2 bg-sky-500 hover:bg-sky-600 dark:bg-[#0e639c] dark:hover:bg-[#1177bb] text-white text-sm font-medium rounded transition-colors duration-200 focus:outline-none"
            >
              登录
            </button>
            
            <div class="text-sm text-gray-600 dark:text-gray-400">
              没有账号？
              <a href="#" class="text-sky-500 hover:text-sky-600 dark:text-sky-400 hover:underline font-medium transition-colors duration-200">
                注册
              </a>
            </div>
          </div>
  
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { reactive } from 'vue'
  
  // 接收父组件传来的控制显示隐藏的 props
  const props = defineProps({
    visible: {
      type: Boolean,
      default: false
    }
  })
  
  // 定义抛出给父组件的事件
  const emit = defineEmits(['update:visible', 'login-success'])
  
  // 表单响应式数据
  const form = reactive({
    phone: '',
    password: '',
    remember: false
  })
  
  // 关闭弹窗
  const closeModal = () => {
    emit('update:visible', false)
  }
  
  // 点击登录
  const handleLogin = () => {
    if (!form.phone || !form.password) {
      alert('请输入手机号和密码')
      return
    }
    
    // 这里模拟调用接口
    console.log('提交登录表单:', form)
    
    // 假设登录成功，关闭弹窗并通知父组件
    // closeModal()
    // emit('login-success', form)
  }
  </script>