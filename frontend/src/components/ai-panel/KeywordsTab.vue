<script setup lang="ts">
import { onMounted } from 'vue'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'

const aiStore = useAiStore()
const libraryStore = useLibraryStore()

// Demo keywords for display
const demoKeywords = [
  { term: 'Chain-of-Thought', definition: '一种促使大型语言模型生成中间推理步骤的技术' },
  { term: 'Faithfulness', definition: '模型输出与其内部推理过程的一致程度' },
  { term: 'Internal Alignment', definition: '模型行为与其设计目标之间的对齐程度' },
  { term: 'Reasoning Traces', definition: '模型在解决问题时产生的推理步骤序列' },
  { term: 'Prompt Engineering', definition: '设计输入提示以获得更好模型输出的技术' },
]

onMounted(() => {
  if (aiStore.keywords.length === 0 && libraryStore.currentDocument) {
    // For demo, use mock data
    aiStore.setKeywords(demoKeywords.map(k => ({
      ...k,
      occurrences: [{ pageNumber: 1, position: [0, 0, 100, 20] as [number, number, number, number] }]
    })))
  }
})

function handleKeywordClick(term: string) {
  // TODO: Jump to first occurrence in PDF
  console.log('Jump to keyword:', term)
}
</script>

<template>
  <div class="h-full overflow-y-auto p-4">
    <div class="mb-4">
      <h3 class="text-sm font-medium text-gray-700 mb-2">专业术语</h3>
      <p class="text-xs text-gray-500">点击术语可跳转至文中出现位置</p>
    </div>

    <!-- Loading State -->
    <div v-if="aiStore.isLoadingKeywords" class="flex items-center justify-center py-8">
      <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
    </div>

    <!-- Keywords List -->
    <div v-else-if="aiStore.keywords.length > 0" class="space-y-3">
      <div
        v-for="keyword in aiStore.keywords"
        :key="keyword.term"
        @click="handleKeywordClick(keyword.term)"
        class="p-3 bg-gray-50 rounded-lg hover:bg-primary-50 cursor-pointer transition-colors group"
      >
        <div class="flex items-start gap-2">
          <span class="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs font-medium rounded">
            {{ keyword.term }}
          </span>
          <span class="text-xs text-gray-400">
            {{ keyword.occurrences?.length || 0 }} 处
          </span>
        </div>
        <p v-if="keyword.definition" class="mt-2 text-sm text-gray-600">
          {{ keyword.definition }}
        </p>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-8 text-gray-400">
      <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
      </svg>
      <p class="text-sm">暂无关键词</p>
      <p class="text-xs mt-1">打开文档后自动提取</p>
    </div>
  </div>
</template>
