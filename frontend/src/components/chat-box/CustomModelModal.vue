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
  <div class="absolute inset-0 bg-black/20 backdrop-blur-[1px] z-[60] flex items-center justify-center p-4">
    <div class="bg-white dark:bg-[#252526] rounded-lg w-full max-w-[340px] p-4 border border-blue-100/50 dark:border-slate-800 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
      <div class="space-y-2.5">
        <div>
          <label class="block text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-1 grayscale opacity-80">模型名称 (Model ID)</label>
          <input v-model="newCustomModel.name" type="text" placeholder="e.g. deepseek-chat" class="w-full px-3 py-1.5 text-sm bg-slate-50/50 dark:bg-slate-900/30 border border-blue-100/30 dark:border-slate-700/50 rounded focus:ring-1 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all dark:text-gray-100" />
        </div>
        <div>
          <label class="block text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-1 grayscale opacity-80">API Base URL</label>
          <input v-model="newCustomModel.apiBase" type="text" placeholder="https://api.example.com/v1" class="w-full px-3 py-1.5 text-sm bg-slate-50/50 dark:bg-slate-900/30 border border-blue-100/30 dark:border-slate-700/50 rounded focus:ring-1 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all dark:text-gray-100" />
        </div>
        <div>
          <label class="block text-[11px] font-medium text-slate-500 dark:text-slate-400 mb-1 grayscale opacity-80">API Key</label>
          <input v-model="newCustomModel.apiKey" type="password" placeholder="sk-..." class="w-full px-3 py-1.5 text-sm bg-slate-50/50 dark:bg-slate-900/30 border border-blue-100/30 dark:border-slate-700/50 rounded focus:ring-1 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all dark:text-gray-100" />
        </div>
      </div>
      <div class="flex justify-end gap-2 mt-5">
        <button @click="$emit('close')" class="px-3.5 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">取消</button>
        <button @click="saveCustomModel" class="px-4 py-1.5 text-xs bg-primary-600 text-white hover:bg-primary-700 rounded transition-colors shadow-sm focus:ring-2 focus:ring-primary-500/20">保存模型</button>
      </div>
    </div>
  </div>
</template>
