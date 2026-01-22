<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'

const aiStore = useAiStore()
const libraryStore = useLibraryStore()

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

// Chat session state
const showHistoryPanel = ref(false)

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
  showHistoryPanel.value = false
}

// Chat session handlers
const toggleHistoryPanel = () => {
  showHistoryPanel.value = !showHistoryPanel.value
}

const createNewChat = () => {
  const pdfId = libraryStore.currentDocument?.id
  if (pdfId) {
    aiStore.createNewSession(pdfId)
  }
  showHistoryPanel.value = false
}

const loadChatSession = async (sessionId: string) => {
  await aiStore.loadSession(sessionId)
  showHistoryPanel.value = false
}

const deleteChatSession = async (sessionId: string, event: Event) => {
  event.stopPropagation()
  if (confirm('确定要删除这个对话吗？')) {
    try {
      await aiStore.deleteSession(sessionId)
      // 删除成功，可以显示提示（可选）
      console.log('会话已删除')
    } catch (error) {
      console.error('删除会话失败:', error)
      alert('删除会话失败，请重试')
    }
  }
}

// 获取当前 PDF 的聊天会话列表
const getCurrentPdfSessions = () => {
  const pdfId = libraryStore.currentDocument?.id
  if (!pdfId) return []
  return aiStore.getSessionsByPdfId(pdfId)
}

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  return date.toLocaleDateString('zh-CN')
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

  // Get current PDF ID from library store
  const pdfId = libraryStore.currentDocument?.id
  if (!pdfId) {
    console.error('No PDF selected')
    return
  }

  // 如果没有当前会话，创建新会话
  if (!aiStore.currentSessionId) {
    aiStore.createNewSession(pdfId)
  }

  // 添加用户消息
  aiStore.addChatMessage({
    role: 'user',
    content,
  })

  inputMessage.value = ''
  aiStore.isLoadingChat = true

  // Scroll to bottom
  await nextTick()
  scrollToBottom()

  try {
    // 构建历史消息（排除当前刚添加的用户消息）
    const history = aiStore.chatMessages.slice(0, -1).map(msg => ({
      role: msg.role,
      content: msg.content
    }))

    // 调用后端 API（根据接口文档使用 /api/chatbox/message）
    const response = await fetch('http://localhost:5000/api/chatbox/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: content,
        pdfId,
        userId: 'default_user', // 可选，默认为 default_user
        sessionId: aiStore.currentSessionId, // 保留以便后续后端存储
        history
      })
    })

    const data = await response.json()

    // 添加 AI 回复
    aiStore.addChatMessage({
      role: 'assistant',
      content: data.response,
      citations: data.citations || []
    })
  } catch (error) {
    console.error('Failed to send message:', error)
    aiStore.addChatMessage({
      role: 'assistant',
      content: '抱歉，发生错误，请稍后重试。',
      citations: []
    })
  }

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

// 当PDF变化时，从后端加载该PDF的聊天会话
watch(() => libraryStore.currentDocument?.id, async (pdfId) => {
  if (pdfId) {
    // 清空当前会话
    aiStore.clearChat()
    // 从后端加载该PDF的会话列表
    await aiStore.loadSessionsFromBackend(pdfId)
    console.log(`Loaded chat sessions for PDF: ${pdfId}`)
  }
}, { immediate: true })

// Expose methods for parent component
defineExpose({
  toggleHistoryPanel
})
</script>

<template>
  <div class="h-full flex flex-col relative">
    <!-- Top Toolbar: New Chat Button -->
    <div class="absolute top-3 right-3 z-10 flex gap-2">
      <!-- New Chat Button - Minimalist premium style -->
      <button
        @click="createNewChat"
        class="flex items-center gap-2 px-4 py-2 bg-white/80 dark:bg-[#2d2d30] backdrop-blur-sm hover:bg-white dark:hover:bg-[#3e3e42] border border-gray-200/60 dark:border-gray-700/60 text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white rounded-xl transition-all duration-200 shadow-sm hover:shadow"
        title="新对话"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4v16m8-8H4" />
        </svg>
        <span class="text-sm font-medium">新对话</span>
      </button>
    </div>

    <!-- History Panel (Overlay) -->
    <div
      v-if="showHistoryPanel"
      class="absolute inset-0 bg-black/20 z-20"
      @click="showHistoryPanel = false"
    >
      <div
        class="absolute right-0 top-0 bottom-0 w-80 bg-white/95 dark:bg-[#252526] backdrop-blur-md shadow-2xl border-l border-gray-200/50 dark:border-gray-800/50"
        @click.stop
      >
        <!-- History Header - Premium style -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200 tracking-wide">聊天记录</h3>
          <button
            @click="showHistoryPanel = false"
            class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-all duration-200"
          >
            <svg class="w-4 h-4 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- History List - Clean premium style -->
        <div class="overflow-y-auto" style="height: calc(100% - 65px)">
          <div v-if="getCurrentPdfSessions().length === 0" class="p-8 text-center text-gray-400 text-sm">
            暂无聊天记录
          </div>
          <div
            v-for="session in getCurrentPdfSessions()"
            :key="session.id"
            class="relative group/item"
          >
            <button
              @click="loadChatSession(session.id)"
              class="w-full text-left px-5 py-3.5 pr-12 hover:bg-gray-50/80 dark:hover:bg-[#2d2d30] border-b border-gray-50 dark:border-gray-800 transition-all duration-200"
              :class="{ 'bg-gray-50 dark:bg-[#2d2d30]': session.id === aiStore.currentSessionId }"
            >
              <div class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate mb-1.5 group-hover/item:text-gray-900 dark:group-hover/item:text-white">
                {{ session.title }}
              </div>
              <div class="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                <span>{{ session.messages.length }} 条消息</span>
                <span>{{ formatTime(session.updatedAt) }}</span>
              </div>
            </button>
            <!-- Delete button -->
            <button
              @click="deleteChatSession(session.id, $event)"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover/item:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all"
              title="删除对话"
            >
              <svg class="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages Area -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4"
    >
      <!-- Empty State with Suggested Prompts - Centered premium design -->
      <div v-if="aiStore.chatMessages.length === 0" class="h-full flex flex-col justify-center items-center px-8">
        <div class="text-center mb-8">
          <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100 dark:from-[#2d2d30] dark:to-[#3e3e42] flex items-center justify-center">
            <svg class="w-8 h-8 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <p class="text-sm text-gray-500 dark:text-gray-400 font-medium">有什么想问的？</p>
        </div>

        <!-- Suggested Prompts - Centered with max width -->
        <div class="w-full max-w-md space-y-2.5">
          <button
            v-for="prompt in suggestedPrompts"
            :key="prompt"
            @click="sendMessage(prompt)"
            class="w-full text-center px-5 py-3.5 bg-white dark:bg-[#2d2d30] hover:bg-gray-50 dark:hover:bg-[#3e3e42] border border-gray-100 dark:border-gray-700 hover:border-gray-200 dark:hover:border-gray-600 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-all duration-200 shadow-sm hover:shadow"
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
          <!-- User Message: Clean minimal bubble -->
          <div
            v-if="message.role === 'user'"
            class="px-5 py-3.5 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100/80 dark:from-[#2d2d30] dark:to-[#3e3e42] text-gray-800 dark:text-gray-200 rounded-br-md border border-gray-100/50 dark:border-gray-700/50"
          >
            <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>
          </div>
          
          <!-- Assistant Message: Clean text with subtle styling -->
          <div
            v-else
            class="space-y-3"
          >
            <p class="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>

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

    <!-- Input Area - Premium minimal style -->
    <div class="p-4 border-t border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-[#252526]/50 backdrop-blur-sm" @click.self="closeMenus">
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

      <!-- Input row - Premium minimal design -->
      <div class="flex gap-3">
        <input
          v-model="inputMessage"
          type="text"
          placeholder="输入问题..."
          @keyup.enter="sendMessage()"
          class="flex-1 px-5 py-3 border border-gray-200 dark:border-gray-700 rounded-2xl focus:outline-none focus:border-gray-300 dark:focus:border-gray-600 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-800 text-sm bg-white dark:bg-[#3e3e42] dark:text-gray-200 transition-all duration-200 placeholder:text-gray-400 dark:placeholder:text-gray-500"
        />
        <button
          @click="sendMessage()"
          :disabled="!inputMessage.trim() || aiStore.isLoadingChat"
          class="px-5 py-3 bg-gray-900 dark:bg-[#0e639c] text-white rounded-2xl hover:bg-gray-800 dark:hover:bg-[#1177bb] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-sm hover:shadow"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
