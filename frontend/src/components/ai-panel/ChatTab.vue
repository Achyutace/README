<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAiStore } from '../../stores/ai'

const aiStore = useAiStore()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const suggestedPrompts = [
  '这篇文章的核心是什么？',
  '这篇论文有什么创新点？',
  '有什么局限性或不足？',
  '请解释主要的研究方法'
]

async function sendMessage(message?: string) {
  const content = message || inputMessage.value.trim()
  if (!content) return

  // Add user message
  aiStore.addChatMessage({
    role: 'user',
    content
  })

  inputMessage.value = ''
  aiStore.isLoadingChat = true

  // Scroll to bottom
  await nextTick()
  scrollToBottom()

  // Simulate AI response (in production, call API)
  await new Promise(resolve => setTimeout(resolve, 1500))

  // Mock AI response
  const mockResponses: Record<string, string> = {
    '这篇文章的核心是什么？': '这篇文章主要研究大型语言模型中 Chain-of-Thought (CoT) 推理的可信度问题。核心问题是：当模型展示其"思考过程"时，这些推理步骤是否真实反映了模型的内部计算过程，还是仅仅是看起来合理的事后解释。',
    '这篇论文有什么创新点？': '主要创新点包括：\n1. 系统性地定义和分析了 CoT 忠实度的概念\n2. 提出了评估推理链忠实程度的实验框架\n3. 发现了模型可能生成"不忠实"推理的具体情况',
    '有什么局限性或不足？': '论文的主要局限性包括：\n1. 实验主要基于特定类型的任务，可能无法推广到所有场景\n2. 评估忠实度的方法本身存在一定的主观性\n3. 尚未提出完整的解决方案来确保 CoT 的忠实性',
    '请解释主要的研究方法': '研究方法主要包括：\n1. 设计对照实验，比较模型在不同条件下的推理行为\n2. 分析推理链中的关键步骤与最终答案的关联性\n3. 通过干预实验测试推理步骤是否真正影响模型决策'
  }

  let response = mockResponses[content]
  if (!response) {
    response = `关于"${content}"，这是一个很好的问题。基于论文内容，我的理解是...\n\n[这是一个演示回复，实际使用时会基于 RAG 检索论文内容生成回答]`
  }

  aiStore.addChatMessage({
    role: 'assistant',
    content: response,
    citations: [{ pageNumber: 1, text: '相关引用段落...' }]
  })

  aiStore.isLoadingChat = false

  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function handleCitationClick(pageNumber: number) {
  // TODO: Jump to citation in PDF
  console.log('Jump to page:', pageNumber)
}

watch(() => aiStore.chatMessages.length, () => {
  nextTick(scrollToBottom)
})
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Messages Area -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4"
    >
      <!-- Empty State with Suggested Prompts -->
      <div v-if="aiStore.chatMessages.length === 0" class="h-full flex flex-col justify-center">
        <div class="text-center mb-6">
          <svg class="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p class="text-sm text-gray-500">有什么想问的？</p>
        </div>

        <!-- Suggested Prompts -->
        <div class="space-y-2">
          <button
            v-for="prompt in suggestedPrompts"
            :key="prompt"
            @click="sendMessage(prompt)"
            class="w-full text-left px-4 py-3 bg-gray-50 hover:bg-primary-50 rounded-lg text-sm text-gray-700 transition-colors"
          >
            {{ prompt }}
          </button>
        </div>
      </div>

      <!-- Chat Messages -->
      <template v-else>
        <div
          v-for="message in aiStore.chatMessages"
          :key="message.id"
          :class="[
            'max-w-[85%]',
            message.role === 'user' ? 'ml-auto' : 'mr-auto'
          ]"
        >
          <div
            :class="[
              'px-4 py-3 rounded-2xl',
              message.role === 'user'
                ? 'bg-primary-600 text-white rounded-br-md'
                : 'bg-gray-100 text-gray-800 rounded-bl-md'
            ]"
          >
            <p class="text-sm whitespace-pre-wrap">{{ message.content }}</p>

            <!-- Citations -->
            <div
              v-if="message.citations && message.citations.length > 0"
              class="mt-2 pt-2 border-t border-gray-200"
            >
              <p class="text-xs text-gray-500 mb-1">引用来源：</p>
              <button
                v-for="citation in message.citations"
                :key="citation.pageNumber"
                @click="handleCitationClick(citation.pageNumber)"
                class="text-xs text-primary-600 hover:underline"
              >
                第 {{ citation.pageNumber }} 页
              </button>
            </div>
          </div>
          <p class="text-xs text-gray-400 mt-1 px-1">
            {{ message.timestamp.toLocaleTimeString() }}
          </p>
        </div>

        <!-- Loading Indicator -->
        <div v-if="aiStore.isLoadingChat" class="flex items-center gap-2 text-gray-500">
          <div class="flex gap-1">
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
          </div>
          <span class="text-sm">正在思考...</span>
        </div>
      </template>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-t border-gray-200">
      <div class="flex gap-2">
        <input
          v-model="inputMessage"
          type="text"
          placeholder="输入问题..."
          @keyup.enter="sendMessage()"
          class="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:border-primary-500 text-sm"
        />
        <button
          @click="sendMessage()"
          :disabled="!inputMessage.trim() || aiStore.isLoadingChat"
          class="px-4 py-2 bg-primary-600 text-white rounded-full hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
