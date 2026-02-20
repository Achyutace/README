<script setup lang="ts">
import { ref } from 'vue'
import { deriveKeyFromPin, encryptData, decryptData } from '../../utils/crypto'
import type { CustomModel } from '../../types'

const props = defineProps<{
  customModels: CustomModel[]
}>()

const emit = defineEmits<{
  (e: 'unlocked', models: CustomModel[]): void
  (e: 'cancel'): void
}>()

const pinCode = ref('')
const isPinUnlocking = ref(false)

const handlePinSubmit = async () => {
  if (!pinCode.value) return alert("请输入 PIN 码")
  isPinUnlocking.value = true
  
  try {
    const key = await deriveKeyFromPin(pinCode.value)
    const storedModelsCipher = localStorage.getItem('readme_custom_models_encrypted')
    
    // 如果系统没有密文，说明这是第一次设定或者覆盖存储
    if (!storedModelsCipher) {
      const { cipher, iv } = await encryptData(JSON.stringify(props.customModels), key)
      localStorage.setItem('readme_custom_models_encrypted', JSON.stringify({ cipher, iv }))
      sessionStorage.setItem('readme_custom_models_session', JSON.stringify(props.customModels))
      alert("加密设定成功。")
      emit('unlocked', props.customModels)
    } else {
      // 正在解密或保存更新覆盖
      const parsedCipher = JSON.parse(storedModelsCipher)
      const plainText = await decryptData(parsedCipher.cipher, parsedCipher.iv, key)
      
      let finalModels = props.customModels
      if (props.customModels.length === 0) {
        finalModels = JSON.parse(plainText) // 恢复
      } else {
        // 更新加密
        const { cipher, iv } = await encryptData(JSON.stringify(props.customModels), key)
        localStorage.setItem('readme_custom_models_encrypted', JSON.stringify({ cipher, iv }))
      }
      
      // 刷新 Session 留存
      sessionStorage.setItem('readme_custom_models_session', JSON.stringify(finalModels))
      emit('unlocked', finalModels)
    }
  } catch (err) {
    alert("PIN 码错误或数据损坏无法解密：" + (err instanceof Error ? err.message : String(err)))
  } finally {
    isPinUnlocking.value = false
    pinCode.value = ''
  }
}

const cancelPinModal = () => {
  pinCode.value = ''
  emit('cancel')
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="bg-gray-800 rounded-xl w-80 p-6 shadow-2xl border border-gray-700 mx-4">
      <h3 class="text-white font-medium mb-3 flex items-center">
        <svg class="w-5 h-5 text-yellow-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
        </svg>
        安全解锁配置
      </h3>
      <p class="text-xs text-gray-400 mb-4 tracking-wider leading-relaxed">
        检测到本地 API 密钥加密库。首次设定或重启浏览器后必须通过唯一的安全 PIN 码开启此组件。
      </p>
      
      <form @submit.prevent="handlePinSubmit">
        <input 
          v-model="pinCode" 
          type="password"
          autocomplete="current-password"
          placeholder="请输入/设定您的安全 PIN" 
          class="w-full bg-gray-900/80 border border-gray-700 text-white px-4 py-2 rounded-lg 
                 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 mb-5 
                 tracking-widest"
          autofocus
        />
        <div class="flex justify-end space-x-3">
          <button 
            type="button" 
            @click="cancelPinModal" 
            class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors border border-transparent hover:border-gray-700 rounded-md"
          >
            忽略
          </button>
          <button 
            type="submit" 
            :disabled="isPinUnlocking"
            class="px-5 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md shadow flex items-center disabled:opacity-50"
          >
            <svg v-if="isPinUnlocking" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isPinUnlocking ? '验证中...' : '提交' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
