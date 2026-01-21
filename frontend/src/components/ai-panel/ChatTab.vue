<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAiStore } from '../../stores/ai'

const aiStore = useAiStore()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

// @ Menu state
const showAtMenu = ref(false)
const showKeywordSubmenu = ref(false)
const selectedReferences = ref<{ type: string; label: string; id: string }[]>([])

// Mock keyword indexes
const keywordIndexes = [
  { id: 'kw1', label: 'Chain-of-Thought' },
  { id: 'kw2', label: 'Unlearning' },
  { id: 'kw3', label: 'Fast-slow-VLA' },
]

// File attachment state
const fileInput = ref<HTMLInputElement | null>(null)
const attachedFiles = ref<{ name: string; id: string }[]>([])

// Model selector state
const showModelMenu = ref(false)
const showMoreModels = ref(false)
const selectedModel = ref('README Fusion')

const premiumModels = [
  { id: 'gpt', name: 'GPT-5.1' },
  { id: 'claude', name: 'Claude Sonnet 4.5' },
  { id: 'gemini', name: 'Gemini 3 Pro Preview' },
]

const basicModels = [
  { id: 'gpt35', name: 'GPT-3.5 Turbo' },
  { id: 'llama', name: 'Llama 3' },
]

const otherModels = [
  { id: 'mistral', name: 'Mistral Large' },
  { id: 'qwen', name: 'Qwen 2.5' },
  { id: 'deepseek', name: 'DeepSeek V3' },
]

// @ Menu handlers
const toggleAtMenu = () => {
  showAtMenu.value = !showAtMenu.value
  if (!showAtMenu.value) {
    showKeywordSubmenu.value = false
  }
}

const handleKeywordClick = () => {
  showKeywordSubmenu.value = !showKeywordSubmenu.value
}

const selectFrameMode = () => {
  // TODO: Implement frame selection mode
  console.log('Frame selection mode activated')
  showAtMenu.value = false
  showKeywordSubmenu.value = false
}

const selectKeywordIndex = (kw: { id: string; label: string }) => {
  if (!selectedReferences.value.find(r => r.id === kw.id)) {
    selectedReferences.value.push({ type: 'keyword', label: kw.label, id: kw.id })
  }
  showAtMenu.value = false
  showKeywordSubmenu.value = false
}

const removeReference = (id: string) => {
  selectedReferences.value = selectedReferences.value.filter(r => r.id !== id)
}

// File handlers
const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    for (const file of target.files) {
      attachedFiles.value.push({ name: file.name, id: Date.now().toString() + file.name })
    }
  }
  target.value = '' // Reset input
}

const removeFile = (id: string) => {
  attachedFiles.value = attachedFiles.value.filter(f => f.id !== id)
}

// Model handlers
const toggleModelMenu = () => {
  showModelMenu.value = !showModelMenu.value
  showMoreModels.value = false
}

const selectModel = (model: { id: string; name: string } | string) => {
  selectedModel.value = typeof model === 'string' ? model : model.name
  showModelMenu.value = false
  showMoreModels.value = false
}

const toggleMoreModels = () => {
  showMoreModels.value = !showMoreModels.value
}

// Close menus when clicking outside
const closeMenus = () => {
  showAtMenu.value = false
  showKeywordSubmenu.value = false
  showModelMenu.value = false
  showMoreModels.value = false
}

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
            message.role === 'user' ? 'max-w-[85%] ml-auto' : 'w-full'
          ]"
        >
          <!-- User Message: lighter bubble -->
          <div
            v-if="message.role === 'user'"
            class="px-4 py-3 rounded-2xl bg-primary-100 text-primary-900 rounded-br-md"
          >
            <p class="text-sm whitespace-pre-wrap">{{ message.content }}</p>
          </div>
          
          <!-- Assistant Message: no frame, like normal text -->
          <div
            v-else
            class="px-2 py-2"
          >
            <p class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>

            <!-- Citations -->
            <div
              v-if="message.citations && message.citations.length > 0"
              class="mt-3 pt-2 border-t border-gray-200"
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
          <p class="text-xs text-gray-400 mt-1 px-1" :class="message.role === 'user' ? 'text-right' : ''">
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
    <div class="p-4 border-t border-gray-200" @click.self="closeMenus">
      <!-- Preview boxes for selected references and files -->
      <div v-if="selectedReferences.length > 0 || attachedFiles.length > 0" class="flex flex-wrap gap-1.5 mb-2">
        <!-- Reference previews -->
        <div
          v-for="ref in selectedReferences"
          :key="ref.id"
          class="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs"
        >
          <span class="text-primary-500">@</span>
          <span class="max-w-20 truncate">{{ ref.label }}</span>
          <button @click="removeReference(ref.id)" class="hover:text-primary-900">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <!-- File previews -->
        <div
          v-for="file in attachedFiles"
          :key="file.id"
          class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
          <span class="max-w-20 truncate">{{ file.name }}</span>
          <button @click="removeFile(file.id)" class="hover:text-gray-900">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>

      <!-- Toolbar buttons -->
      <div class="flex items-center gap-1 mb-2">
        <!-- @ Button with popup -->
        <div class="relative">
          <button
            @click="toggleAtMenu"
            class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors text-sm font-medium"
            :class="{ 'bg-gray-100 text-gray-700': showAtMenu }"
            title="插入引用"
          >
            @
          </button>
          <!-- @ Popup Menu -->
          <div
            v-if="showAtMenu"
            class="absolute bottom-full left-0 mb-1 bg-gray-800/90 rounded-lg shadow-lg py-1 min-w-36 z-50"
          >
            <!-- 本文关键词 -->
            <div class="relative">
              <button
                @click="handleKeywordClick"
                class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center justify-between"
              >
                <span>本文关键词</span>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
              </button>
              <!-- Keyword submenu -->
              <div
                v-if="showKeywordSubmenu"
                class="absolute left-full top-0 ml-1 bg-gray-800/90 rounded-lg shadow-lg py-1 min-w-32"
              >
                <button
                  @click="selectFrameMode"
                  class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center gap-2"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></svg>
                  框选模式
                </button>
                <div class="border-t border-gray-600 my-1"></div>
                <div class="px-2 py-1 text-xs text-gray-400">已建立索引</div>
                <button
                  v-for="kw in keywordIndexes"
                  :key="kw.id"
                  @click="selectKeywordIndex(kw)"
                  class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-gray-700/50"
                >
                  {{ kw.label }}
                </button>
              </div>
            </div>
            <!-- 已读论文 -->
            <button class="w-full text-left px-3 py-2 text-sm text-gray-400 cursor-not-allowed">
              已读论文
            </button>
            <!-- 个人笔记 -->
            <button class="w-full text-left px-3 py-2 text-sm text-gray-400 cursor-not-allowed">
              个人笔记
            </button>
          </div>
        </div>

        <!-- Paperclip Button -->
        <button
          @click="triggerFileInput"
          class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          title="添加文件"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
        </button>
        <input
          ref="fileInput"
          type="file"
          multiple
          class="hidden"
          @change="handleFileSelect"
        />

        <!-- Model Selector -->
        <div class="relative ml-auto">
          <button
            @click="toggleModelMenu"
            class="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 text-gray-600 hover:text-gray-800 transition-colors text-xs"
            :class="{ 'bg-gray-100': showModelMenu }"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
            <span>{{ selectedModel }}</span>
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
          </button>
          <!-- Model Dropdown -->
          <div
            v-if="showModelMenu"
            class="absolute bottom-full right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-44 z-50"
          >
            <!-- README Fusion -->
            <button
              @click="selectModel('README Fusion')"
              class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
              :class="{ 'text-primary-600 bg-primary-50': selectedModel === 'README Fusion' }"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              README Fusion
            </button>
            <div class="border-t border-gray-200 my-1"></div>
            <!-- Premium Models -->
            <div class="px-3 py-1 text-xs text-gray-400 font-medium">高级模型</div>
            <button
              v-for="model in premiumModels"
              :key="model.id"
              @click="selectModel(model)"
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
              :class="{ 'text-primary-600 bg-primary-50': selectedModel === model.name }"
            >
              {{ model.name }}
            </button>
            <div class="border-t border-gray-200 my-1"></div>
            <!-- Basic Models -->
            <div class="px-3 py-1 text-xs text-gray-400 font-medium">初级模型</div>
            <button
              v-for="model in basicModels"
              :key="model.id"
              @click="selectModel(model)"
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
              :class="{ 'text-primary-600 bg-primary-50': selectedModel === model.name }"
            >
              {{ model.name }}
            </button>
            <div class="border-t border-gray-200 my-1"></div>
            <!-- More Models -->
            <div class="relative">
              <button
                @click="toggleMoreModels"
                class="w-full text-left px-3 py-2 text-sm text-gray-500 hover:bg-gray-50 flex items-center justify-center"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
              </button>
              <!-- Other models submenu -->
              <div
                v-if="showMoreModels"
                class="absolute right-full top-0 mr-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-36"
              >
                <div class="px-3 py-1 text-xs text-gray-400 font-medium">其他模型</div>
                <button
                  v-for="model in otherModels"
                  :key="model.id"
                  @click="selectModel(model)"
                  class="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
                  :class="{ 'text-primary-600 bg-primary-50': selectedModel === model.name }"
                >
                  {{ model.name }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input row -->
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
