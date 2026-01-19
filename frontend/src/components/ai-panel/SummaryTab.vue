<script setup lang="ts">
import { onMounted } from 'vue'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'

const aiStore = useAiStore()
const libraryStore = useLibraryStore()

// Demo summary for display
const demoSummary = {
  bullets: [
    '本文研究了大型语言模型中 Chain-of-Thought (CoT) 推理的可信度问题，探讨模型生成的推理步骤是否真实反映其内部计算过程。',
    '研究发现 CoT 推理存在不忠实的情况：模型可能生成看似合理但与其实际决策过程不符的推理链，这对 AI 可解释性提出挑战。',
    '论文提出了评估 CoT 忠实度的方法框架，并讨论了提高推理透明度的潜在改进方向。'
  ],
  generatedAt: new Date()
}

onMounted(() => {
  if (!aiStore.summary && libraryStore.currentDocument) {
    // For demo, use mock data
    aiStore.setSummary(demoSummary)
  }
})

async function regenerateSummary() {
  aiStore.isLoadingSummary = true
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1500))
  aiStore.setSummary({
    ...demoSummary,
    generatedAt: new Date()
  })
  aiStore.isLoadingSummary = false
}
</script>

<template>
  <div class="h-full overflow-y-auto p-4">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm font-medium text-gray-700">三行摘要</h3>
        <p class="text-xs text-gray-500">核心贡献、创新点、局限性</p>
      </div>
      <button
        @click="regenerateSummary"
        :disabled="aiStore.isLoadingSummary"
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
        title="重新生成"
      >
        <svg
          :class="['w-4 h-4 text-gray-500', { 'animate-spin': aiStore.isLoadingSummary }]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="aiStore.isLoadingSummary" class="space-y-3">
      <div v-for="i in 3" :key="i" class="animate-pulse">
        <div class="h-4 bg-gray-200 rounded w-full mb-2"></div>
        <div class="h-4 bg-gray-200 rounded w-5/6"></div>
      </div>
    </div>

    <!-- Summary Content -->
    <div v-else-if="aiStore.summary" class="space-y-4">
      <div
        v-for="(bullet, index) in aiStore.summary.bullets"
        :key="index"
        class="flex gap-3 p-3 bg-gray-50 rounded-lg"
      >
        <span class="flex-shrink-0 w-6 h-6 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-sm font-medium">
          {{ index + 1 }}
        </span>
        <p class="text-sm text-gray-700 leading-relaxed">
          {{ bullet }}
        </p>
      </div>

      <p class="text-xs text-gray-400 text-right">
        生成于 {{ aiStore.summary.generatedAt.toLocaleTimeString() }}
      </p>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-8 text-gray-400">
      <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="text-sm">暂无摘要</p>
      <p class="text-xs mt-1">打开文档后自动生成</p>
    </div>
  </div>
</template>
