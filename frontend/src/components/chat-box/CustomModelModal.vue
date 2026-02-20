<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'save', model: { name: string; apiBase: string; apiKey: string }): void
  (e: 'close'): void
}>()

const newCustomModel = ref({ name: '', apiBase: '', apiKey: '' })

const saveCustomModel = () => {
  if (!newCustomModel.value.name || !newCustomModel.value.apiBase) {
    alert('请填写模型名称和 API Base')
    return
  }
  emit('save', { ...newCustomModel.value })
}
</script>

<template>
  <div class="absolute inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
    <div class="bg-white dark:bg-[#252526] rounded-xl w-full max-w-sm p-5 border border-gray-200 dark:border-gray-700">
      <h3 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-100">自定义模型</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-gray-500 mb-1">模型名称 (Model Name)</label>
          <input v-model="newCustomModel.name" type="text" placeholder="e.g. deepseek-chat" class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">API Base URL</label>
          <input v-model="newCustomModel.apiBase" type="text" placeholder="https://api.example.com/v1" class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">API Key</label>
          <input v-model="newCustomModel.apiKey" type="password" placeholder="sk-..." class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
        </div>
      </div>
      <div class="flex gap-2 mt-6">
        <button @click="$emit('close')" class="flex-1 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg dark:text-gray-300 dark:hover:bg-gray-700">取消</button>
        <button @click="saveCustomModel" class="flex-1 px-4 py-2 text-sm text-white bg-primary-600 hover:bg-primary-700 rounded-lg">保存 (本地)</button>
      </div>
    </div>
  </div>
</template>
