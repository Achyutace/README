<script setup lang="ts">
import { useAiStore } from '../../stores/ai'

const aiStore = useAiStore()
</script>

<template>
  <div class="h-full overflow-y-auto p-4">
    <div class="mb-4">
      <h3 class="text-sm font-medium text-gray-700 mb-1">段落翻译</h3>
      <p class="text-xs text-gray-500">选中文本或滚动到段落时显示翻译</p>
    </div>

    <!-- Loading State -->
    <div v-if="aiStore.isLoadingTranslation" class="flex flex-col items-center justify-center py-8">
      <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mb-3"></div>
      <p class="text-sm text-gray-500">正在翻译...</p>
    </div>

    <!-- Translation Content -->
    <div v-else-if="aiStore.currentTranslation" class="space-y-4">
      <!-- Original Text -->
      <div class="p-3 bg-gray-50 rounded-lg">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xs font-medium text-gray-500 uppercase tracking-wider">原文</span>
          <span class="text-xs text-gray-400">EN</span>
        </div>
        <p class="text-sm text-gray-700 leading-relaxed">
          {{ aiStore.currentTranslation.originalText }}
        </p>
      </div>

      <!-- Arrow -->
      <div class="flex justify-center">
        <svg class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>

      <!-- Translated Text -->
      <div class="p-3 bg-primary-50 rounded-lg border border-primary-100">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xs font-medium text-primary-600 uppercase tracking-wider">译文</span>
          <span class="text-xs text-primary-400">ZH</span>
        </div>
        <div class="space-y-2">
          <p
            v-for="sentence in aiStore.currentTranslation.sentences"
            :key="sentence.index"
            class="text-sm text-gray-700 leading-relaxed"
          >
            <span class="text-xs text-primary-500 font-medium mr-1">[{{ sentence.index }}]</span>
            {{ sentence.translated }}
          </p>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-8 text-gray-400">
      <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
      </svg>
      <p class="text-sm">暂无翻译</p>
      <p class="text-xs mt-1">选中 PDF 中的文本开始翻译</p>

      <!-- Tips -->
      <div class="mt-6 text-left bg-gray-50 rounded-lg p-3">
        <p class="text-xs font-medium text-gray-600 mb-2">使用提示：</p>
        <ul class="text-xs text-gray-500 space-y-1">
          <li class="flex items-start gap-2">
            <span class="text-primary-500">•</span>
            在 PDF 中选中文本，点击"翻译"
          </li>
          <li class="flex items-start gap-2">
            <span class="text-primary-500">•</span>
            开启"自动翻译"实时显示译文
          </li>
          <li class="flex items-start gap-2">
            <span class="text-primary-500">•</span>
            句子编号与原文一一对应
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
