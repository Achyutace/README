<template>
    <div 
      class="fixed inset-0 z-50 flex items-center justify-center bg-blue-500/40"
    >
      <div class="w-[420px] bg-white dark:bg-[#252526] border border-gray-200 dark:border-[#3e3e42] rounded-lg shadow-xl overflow-hidden flex flex-col transform transition-all duration-300">
        
        <div class="px-6 py-4 bg-gray-50 dark:bg-[#2d2d30] border-b border-gray-200 dark:border-[#3e3e42] flex justify-between items-center">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            用户注册
          </h3>
          <button @click="closeModal" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors duration-200">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
  
        <div class="p-6 flex flex-col gap-4">
          
          <div>
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">用户名</label>
            <input 
              v-model="form.username" 
              type="text" 
              placeholder="请输入用户名"
              class="w-full px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200" 
            />
          </div>
  
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
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">验证码</label>
            <div class="flex gap-2">
              <input 
                v-model="form.code" 
                type="text" 
                placeholder="请输入验证码"
                class="flex-1 px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200" 
              />
              <button 
                @click="getVerificationCode"
                :disabled="countdown > 0"
                class="whitespace-nowrap px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-[#3e3e42] dark:hover:bg-[#4d4d50] text-gray-700 dark:text-gray-200 text-sm font-medium rounded transition-colors duration-200 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ countdown > 0 ? `${countdown}s 后重试` : '获取验证码' }}
              </button>
            </div>
          </div>
  
          <div>
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">密码</label>
            <input 
              v-model="form.password" 
              type="password" 
              placeholder="设置密码"
              class="w-full px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200" 
            />
          </div>
  
          <div>
            <label class="block text-sm mb-1.5 text-gray-700 dark:text-gray-300">确认密码</label>
            <input 
              v-model="form.confirmPassword" 
              type="password" 
              placeholder="请再次输入密码"
              class="w-full px-3 py-2 bg-white dark:bg-[#3e3e42] border border-gray-200 dark:border-[#3e3e42] rounded text-gray-900 dark:text-gray-100 focus:outline-none focus:border-sky-500 dark:focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors duration-200" 
            />
          </div>
  
          <div class="flex justify-between items-center mt-4 pt-2">
            <button 
              @click="handleRegister"
              class="px-6 py-2 bg-sky-500 hover:bg-sky-600 dark:bg-[#0e639c] dark:hover:bg-[#1177bb] text-white text-sm font-medium rounded transition-colors duration-200 focus:outline-none"
            >
              注册
            </button>
            
            <div class="text-sm text-gray-600 dark:text-gray-400">
              已有账号？
              <button @click="switchToLogin" class="text-sky-500 hover:text-sky-600 dark:text-sky-400 hover:underline font-medium transition-colors duration-200 focus:outline-none">
                登录
              </button>
            </div>
          </div>
  
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { reactive, ref } from 'vue'
  
  const props = defineProps({
    visible: {
      type: Boolean,
      default: false
    }
  })
  
  // update:visible 控制弹窗开关，switch-to-login 用于通知父组件切换到登录组件
  const emit = defineEmits(['update:visible', 'register-success', 'switch-to-login'])
  
  const form = reactive({
    username: '',
    phone: '',
    code: '',
    password: '',
    confirmPassword: ''
  })
  
  const countdown = ref(0)
  let timer = null
  
  // 关闭弹窗
  const closeModal = () => {
    emit('update:visible', false)
  }
  
  // 切换到登录界面
  const switchToLogin = () => {
    emit('switch-to-login')
  }
  
  // 获取验证码
  const getVerificationCode = () => {
  
    // 模拟发送验证码接口调用
    console.log('向手机号发送验证码:', form.code)
    
    // 开启倒计时
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(timer)
      }
    }, 1000)
  }
  
  // 点击注册
  const handleRegister = () => {
    if (!form.username || !form.phone || !form.code || !form.password || !form.confirmPassword) {
      alert('请填写完整注册信息')
      return
    }
  
    if (form.password !== form.confirmPassword) {
      alert('两次输入的密码不一致')
      return
    }
    
    // 这里模拟调用注册接口
    console.log('提交注册表单:', form)
    
    // 假设注册成功
    // alert('注册成功，请登录！')
    // switchToLogin()
  }
  </script>