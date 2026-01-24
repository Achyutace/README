<script setup lang="ts">
import { ref, nextTick, watch, onMounted, computed, reactive } from 'vue'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'
import { usePdfStore } from '../../stores/pdf'
import { chatSessionApi } from '../../api'

// --- Markdown Imports ---
import MarkdownIt from 'markdown-it'
import type { Options } from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
// 引入代码高亮样式
import 'highlight.js/styles/atom-one-dark.css'

const aiStore = useAiStore()
const libraryStore = useLibraryStore()
const pdfStore = usePdfStore()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

// --- Tooltip State ---
// 控制引用悬浮窗的状态
const tooltipState = reactive({
  visible: false,
  x: 0,
  y: 0,
  content: null as any // 存储当前的引用数据
})
let tooltipTimeout: any = null

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

// --- Feature: Custom Models & Model State ---
const showModelMenu = ref(false)
const showCustomModelModal = ref(false) // 自定义模型弹窗
const selectedModel = ref('README Fusion')

// --- Feature: Chat Mode Toggle ---
const chatMode = ref<'agent' | 'simple'>('agent') 

// 自定义模型数据接口
interface CustomModel {
  id: string
  name: string
  apiBase: string
  apiKey: string
}

const customModels = ref<CustomModel[]>([])
const newCustomModel = ref({ name: '', apiBase: '', apiKey: '' })

// 计算所有可用模型（用于发送时查找配置）
const allAvailableModels = computed(() => {
  return [
    { id: 'default', name: 'README Fusion' },
    ...customModels.value
  ]
})

// --- Feature: Preset Prompts ---
const showPromptMenu = ref(false)
const isEditingPrompts = ref(false) // 编辑模式开关
// 默认提示词
const defaultPrompts = [
  '这篇文章针对的问题的是什么？',
  '这篇论文有什么创新点？',
  '这篇论文有什么局限性或不足？',
  '这篇论文主要的研究方法是什么？',
  '这篇文章启发了哪些后续的研究？',
]
// 用户提示词（包含默认的）
const userPrompts = ref<{id: string, text: string}[]>(
  defaultPrompts.map((p, i) => ({ id: `sys_${i}`, text: p }))
)

// Chat session state 
const showHistoryPanel = ref(false)

// --- Markdown Configuration ---
const md: MarkdownIt = new MarkdownIt({
  html: false, // 禁用 HTML 标签以防注入,使用 DOMPurify 双重保险
  linkify: true, // 自动识别 URL
  breaks: true, // 换行符转换为 <br>
  highlight: function (str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
        }</code></pre>`
      } catch (__) {}
    }
    return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
} as Options)

// 渲染 Markdown 并处理引用标记
const renderMarkdown = (content: string) => {
  if (!content) return ''
  
  // 1. 先进行基础 Markdown 渲染
  let html = md.render(content)

  // 2. 正则替换 [n] 为带有特殊 class 和 data-id 的 span
  // 注意：这里使用了简化的正则，避免替换代码块中的内容可能需要更复杂的逻辑，
  // 但对于标准学术回复 [n] 格式通常足够。
  // 替换逻辑：找到 [数字]，替换为 <span class="citation-ref ...">[数字]</span>
  html = html.replace(/\[(\d+)\]/g, (_match, id) => {
    return `<span class="citation-ref text-primary-600 bg-primary-50 px-1 rounded cursor-pointer font-medium hover:bg-primary-100 transition-colors select-none" data-id="${id}">[${id}]</span>`
  })

  // 3. 净化 HTML，配置允许的标签和属性
  return DOMPurify.sanitize(html, {
    ADD_TAGS: ['iframe'],
    ADD_ATTR: ['target', 'data-id', 'class'] // 关键：允许 data-id 和 class 通过净化
  })
}

// --- Interaction Handlers ---

// 处理鼠标在消息内容上的移动（用于显示 Tooltip）
const handleMessageMouseOver = (event: MouseEvent, citations: any[]) => {
  const target = event.target as HTMLElement
  
  // 如果鼠标悬停在引用标签上
  if (target.classList.contains('citation-ref')) {
    const id = parseInt(target.getAttribute('data-id') || '0')
    const citationData = citations.find(c => c.id === id)
    
    if (citationData) {
      if (tooltipTimeout) clearTimeout(tooltipTimeout)
      
      // 计算位置
      const rect = target.getBoundingClientRect()
      // 相对于视口的位置
      tooltipState.x = rect.left + window.scrollX
      tooltipState.y = rect.top + window.scrollY - 10 // 稍微向上偏移
      tooltipState.content = citationData
      tooltipState.visible = true
    }
  }
}

const handleMessageMouseOut = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (target.classList.contains('citation-ref')) {
    // 延迟隐藏，防止鼠标移向 tooltip 时瞬间消失（如果需要交互 tooltip 内容）
    tooltipTimeout = setTimeout(() => {
      tooltipState.visible = false
      tooltipState.content = null
    }, 300)
  }
}

// 保持 tooltip 显示（当鼠标移入 tooltip 本身时）
const handleTooltipEnter = () => {
  if (tooltipTimeout) clearTimeout(tooltipTimeout)
}

const handleTooltipLeave = () => {
  tooltipState.visible = false
  tooltipState.content = null
}

// 处理点击引用（针对外部链接直接跳转）
const handleMessageClick = (event: MouseEvent, citations: any[]) => {
  const target = event.target as HTMLElement
  if (target.classList.contains('citation-ref')) {
    const id = parseInt(target.getAttribute('data-id') || '0')
    const citationData = citations.find(c => c.id === id)
    
    if (citationData && citationData.source_type === 'external' && citationData.url) {
      window.open(citationData.url, '_blank')
    }
    // 本地引用点击暂时不做跳转，或者可以滚动到底部列表
  }
}

// Lifecycle
onMounted(() => {
  // 从 localStorage 加载自定义模型
  const storedModels = localStorage.getItem('readme_custom_models')
  if (storedModels) {
    customModels.value = JSON.parse(storedModels)
  }
  
  // TODO: 从后端加载用户预设提示词
  // fetchUserPrompts()
})

// @ Menu handlers
const toggleAtMenu = () => {
  showAtMenu.value = !showAtMenu.value
  if (!showAtMenu.value) showKeywordSubmenu.value = false
  closeOtherMenus('at')
}

const handleKeywordClick = () => {
  showKeywordSubmenu.value = !showKeywordSubmenu.value
}

const selectFrameMode = () => {
  console.log('Frame selection mode activated')
  closeMenus()
}

const selectKeywordIndex = (kw: { id: string; label: string }) => {
  if (!selectedReferences.value.find(r => r.id === kw.id)) {
    selectedReferences.value.push({ type: 'keyword', label: kw.label, id: kw.id })
  }
  closeMenus()
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
  target.value = '' 
}

const removeFile = (id: string) => {
  attachedFiles.value = attachedFiles.value.filter(f => f.id !== id)
}

// --- Prompt Handlers ---
const togglePromptMenu = () => {
  showPromptMenu.value = !showPromptMenu.value
  // Reset edit mode when opening
  if (showPromptMenu.value) isEditingPrompts.value = false
  closeOtherMenus('prompt')
}

const handlePromptClick = (promptText: string) => {
  // 直接发送
  sendMessage(promptText)
  showPromptMenu.value = false
}

const toggleEditPrompts = () => {
  isEditingPrompts.value = !isEditingPrompts.value
}

const addNewPrompt = () => {
  userPrompts.value.push({ id: `new_${Date.now()}`, text: '' })
}

const removePrompt = (index: number) => {
  userPrompts.value.splice(index, 1)
}

const savePrompts = async () => {
  // 过滤空提示词
  userPrompts.value = userPrompts.value.filter(p => p.text.trim() !== '')
  
  // 模拟发送到后端
  try {
    console.log('Saving prompts to backend for user: default_user', userPrompts.value)
    // const response = await fetch('/api/user/prompts', { method: 'POST', body: ... })
    isEditingPrompts.value = false
  } catch (error) {
    console.error('Failed to save prompts', error)
  }
}

// --- Model Handlers ---
const toggleModelMenu = () => {
  showModelMenu.value = !showModelMenu.value
  closeOtherMenus('model')
}

const selectModel = (modelName: string) => {
  selectedModel.value = modelName
  showModelMenu.value = false
}

// --- Chat Mode Handlers ---
const toggleChatMode = () => {
  chatMode.value = chatMode.value === 'agent' ? 'simple' : 'agent'
  console.log('Chat mode switched to:', chatMode.value)
}

const openCustomModelModal = () => {
  newCustomModel.value = { name: '', apiBase: '', apiKey: '' }
  showCustomModelModal.value = true
  showModelMenu.value = false
}

const saveCustomModel = () => {
  if (!newCustomModel.value.name || !newCustomModel.value.apiBase) {
    alert('请填写模型名称和 API Base')
    return
  }
  
  const modelToAdd: CustomModel = {
    id: `custom_${Date.now()}`,
    ...newCustomModel.value
  }
  
  customModels.value.push(modelToAdd)
  localStorage.setItem('readme_custom_models', JSON.stringify(customModels.value))
  
  selectedModel.value = modelToAdd.name
  showCustomModelModal.value = false
}

const deleteCustomModel = (id: string, event: Event) => {
  event.stopPropagation()
  const modelToDelete = customModels.value.find(m => m.id === id)
  if (modelToDelete && confirm('确定删除该自定义模型？')) {
    customModels.value = customModels.value.filter(m => m.id !== id)
    localStorage.setItem('readme_custom_models', JSON.stringify(customModels.value))
    if (selectedModel.value === modelToDelete.name) {
      selectedModel.value = 'README Fusion'
    }
  }
}

// Utility to manage menus
const closeOtherMenus = (active: 'at' | 'model' | 'prompt') => {
  if (active !== 'at') { showAtMenu.value = false; showKeywordSubmenu.value = false }
  if (active !== 'model') { showModelMenu.value = false }
  if (active !== 'prompt') { showPromptMenu.value = false }
}

const closeMenus = () => {
  showAtMenu.value = false
  showKeywordSubmenu.value = false
  showModelMenu.value = false
  showPromptMenu.value = false
  showHistoryPanel.value = false
}

// Chat session handlers
const toggleHistoryPanel = () => {
  showHistoryPanel.value = !showHistoryPanel.value
}

const createNewChat = async () => {
  const pdfId = libraryStore.currentDocument?.id
  if (pdfId) {
    await aiStore.createNewSession(pdfId)
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
    } catch (error) {
      console.error('删除会话失败:', error)
    }
  }
}

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

// --- Send Message Logic (Updated) ---
async function sendMessage(message?: string) {
  const content = message || inputMessage.value.trim()
  if (!content) return
  const pdfId = libraryStore.currentDocument?.id
  if (!pdfId) {
    console.error('No PDF selected')
    return
  }
  // 如果没有会话ID，先创建一个
  if (!aiStore.currentSessionId) {
    await aiStore.createNewSession(pdfId)
  }
  // 乐观更新 UI
  aiStore.addChatMessage({ role: 'user', content })
  inputMessage.value = ''
  aiStore.isLoadingChat = true
  await nextTick()
  scrollToBottom()
  try {
    // 获取当前选中的自定义模型配置
    const currentModelConfig = allAvailableModels.value.find(m => m.name === selectedModel.value)
    // 调用封装的 API
    const data = await chatSessionApi.sendMessage(
      aiStore.currentSessionId!,
      content,
      pdfId,
      chatMode.value,
      selectedModel.value,
      (currentModelConfig as CustomModel)?.apiBase,
      (currentModelConfig as CustomModel)?.apiKey
    )
    aiStore.addChatMessage({
      role: 'assistant',
      content: data.response,
      citations: data.citations || []
    })
  } catch (error) {
    console.error('Failed to send message:', error)
    aiStore.addChatMessage({
      role: 'assistant',
      content: '抱歉，网络请求失败，请检查后端服务。',
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

watch(() => aiStore.chatMessages.length, () => {
  nextTick(scrollToBottom)
})

watch(() => libraryStore.currentDocument?.id, async (pdfId) => {
  if (pdfId) {
    aiStore.clearChat()
    await aiStore.loadSessionsFromBackend(pdfId)
  }
}, { immediate: true })

defineExpose({
  toggleHistoryPanel,
  createNewChat
})
</script>

<template>
  <div class="h-full flex flex-col relative">
    
    <!-- Tooltip Component (Global Absolute Position) -->
    <div 
      v-if="tooltipState.visible && tooltipState.content"
      class="fixed z-[100] w-80 bg-white dark:bg-[#2d2d30] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 p-4 transition-opacity duration-200"
      :style="{ left: Math.min(tooltipState.x - 20, 1024) + 'px', top: (tooltipState.y - 10) + 'px', transform: 'translateY(-100%)' }"
      @mouseenter="handleTooltipEnter"
      @mouseleave="handleTooltipLeave"
    >
      <!-- Header: Icon + Type -->
      <div class="flex items-center gap-2 mb-2 text-xs font-bold uppercase tracking-wider text-gray-400">
        <span v-if="tooltipState.content.source_type === 'local'" class="flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          本地文档 - P{{ tooltipState.content.page || 'N/A' }}
        </span>
        <span v-else class="flex items-center gap-1 text-blue-500">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
          网络来源
        </span>
      </div>
      
      <!-- Title -->
      <h4 class="font-semibold text-sm text-gray-800 dark:text-gray-100 mb-2 leading-tight">
        {{ tooltipState.content.title }}
      </h4>

      <!-- Snippet -->
      <p class="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-black/20 p-2 rounded mb-2 border-l-2 border-primary-400 line-clamp-4 italic">
        "{{ tooltipState.content.snippet }}"
      </p>

      <!-- Action Hint -->
      <div v-if="tooltipState.content.source_type === 'external'" class="text-xs text-blue-600 dark:text-blue-400 flex items-center justify-end gap-1">
        点击跳转原文 <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
      </div>
    </div>

    <!-- Custom Model Modal -->
    <div v-if="showCustomModelModal" class="absolute inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
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
          <button @click="showCustomModelModal = false" class="flex-1 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg dark:text-gray-300 dark:hover:bg-gray-700">取消</button>
          <button @click="saveCustomModel" class="flex-1 px-4 py-2 text-sm text-white bg-primary-600 hover:bg-primary-700 rounded-lg">保存 (本地)</button>
        </div>
      </div>
    </div>

    <!-- History Panel (Overlay) -->
    <div
      v-if="showHistoryPanel"
      class="absolute inset-0 bg-black/20 z-20"
      @click="showHistoryPanel = false"
    >
      <div
        class="absolute right-0 top-0 bottom-0 w-80 bg-white/95 dark:bg-[#252526] backdrop-blur-md border-l border-gray-200/50 dark:border-gray-800/50"
        @click.stop
      >
        <!-- History Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200 tracking-wide">聊天记录</h3>
          <button
            @click="showHistoryPanel = false"
            class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-all duration-200"
          >
            <svg class="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <!-- History List -->
        <div class="overflow-y-auto" style="height: calc(100% - 65px)">
          <div v-if="getCurrentPdfSessions().length === 0" class="p-8 text-center text-gray-400 text-sm">暂无聊天记录</div>
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
              <div class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate mb-1.5">{{ session.title }}</div>
              <div class="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                <span>{{ session.messages.length }} 条消息</span>
                <span>{{ formatTime(session.updatedAt) }}</span>
              </div>
            </button>
            <button
              @click="deleteChatSession(session.id, $event)"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover/item:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all"
            >
              <svg class="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages Area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-6">
      <template v-if="aiStore.chatMessages.length > 0">
        <div v-for="message in aiStore.chatMessages" :key="message.id" :class="[message.role === 'user' ? 'max-w-[85%] ml-auto' : 'w-full']">
          
          <!-- User Message -->
          <div v-if="message.role === 'user'" class="px-5 py-3.5 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100/80 dark:from-[#2d2d30] dark:to-[#3e3e42] text-gray-800 dark:text-gray-200 rounded-br-md border border-gray-100/50 dark:border-gray-700/50 shadow-sm">
            <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>
          </div>
          
          <!-- Assistant Message -->
          <div v-else class="space-y-4 pl-1 pr-4">
            <!-- 1. Content with Citations -->
            <div 
              class="markdown-body prose prose-sm max-w-none dark:prose-invert 
                     prose-p:leading-relaxed prose-pre:bg-[#282c34] prose-pre:m-0
                     prose-headings:font-semibold prose-headings:text-gray-800 dark:prose-headings:text-gray-100
                     prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                     text-gray-800 dark:text-gray-200"
              v-html="renderMarkdown(message.content)"
              @mouseover="handleMessageMouseOver($event, message.citations || [])"
              @mouseout="handleMessageMouseOut"
              @click="handleMessageClick($event, message.citations || [])"
            ></div>
            
            <!-- 2. Structured Reference List (Bottom) -->
            <div v-if="message.citations && message.citations.length > 0" class="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/50">
              <h4 class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">参考来源</h4>
              <div class="grid grid-cols-1 gap-2">
                <div 
                  v-for="cite in message.citations" 
                  :key="cite.id"
                  class="flex items-start gap-3 p-2 rounded-lg border border-transparent hover:border-gray-200 dark:hover:border-gray-700 hover:bg-gray-50 dark:hover:bg-[#3e3e42] transition-colors group"
                >
                  <!-- Index Badge -->
                  <div class="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[10px] font-bold text-primary-600 bg-primary-50 rounded mt-0.5">
                    {{ cite.id }}
                  </div>
                  
                  <!-- Content -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <span v-if="cite.source_type === 'local'" class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">PDF</span>
                      <span v-else class="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">Web</span>
                      
                      <a 
                        v-if="cite.source_type === 'external' && cite.url"
                        :href="cite.url" 
                        target="_blank"
                        class="text-xs font-medium text-gray-800 dark:text-gray-200 hover:text-blue-600 dark:hover:text-blue-400 truncate block"
                      >
                        {{ cite.title }}
                      </a>
                      <span v-else class="text-xs font-medium text-gray-800 dark:text-gray-200 truncate block">
                        {{ cite.title }}
                      </span>
                    </div>
                    
                    <p class="text-xs text-gray-400 truncate">
                      {{ cite.snippet }}
                    </p>
                  </div>

                  <!-- Action Icon (External Link) -->
                  <a 
                     v-if="cite.source_type === 'external' && cite.url"
                     :href="cite.url"
                     target="_blank"
                     class="flex-shrink-0 text-gray-300 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                     title="打开链接"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
          
          <p class="text-xs text-gray-400 mt-1 px-1" :class="message.role === 'user' ? 'text-right' : ''">{{ message.timestamp.toLocaleTimeString() }}</p>
        </div>
        
        <div v-if="aiStore.isLoadingChat" class="flex items-center gap-2 text-gray-500 p-4">
          <div class="flex gap-1"><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-75"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-150"></span></div>
          <span class="text-sm">正在深度思考...</span>
        </div>
      </template>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-t border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-[#252526]/50 backdrop-blur-sm" @click.self="closeMenus">
      <!-- Preview boxes -->
      <div v-if="selectedReferences.length > 0 || attachedFiles.length > 0 || pdfStore.selectedText" class="flex flex-wrap gap-1.5 mb-2">
        <!-- PDF Selection Preview -->
        <div v-if="pdfStore.selectedText" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-xs">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" /></svg>
          <span class="max-w-20 truncate" :title="pdfStore.selectedText">{{ pdfStore.selectedText }}</span>
          <button @click="pdfStore.clearSelection()" class="hover:text-gray-900 dark:hover:text-white"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>

        <div v-for="ref in selectedReferences" :key="ref.id" class="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs">
          <span class="text-primary-500">@</span><span class="max-w-20 truncate">{{ ref.label }}</span>
          <button @click="removeReference(ref.id)" class="hover:text-primary-900"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>
        <div v-for="file in attachedFiles" :key="file.id" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
          <span class="max-w-20 truncate">{{ file.name }}</span>
          <button @click="removeFile(file.id)" class="hover:text-gray-900"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>
      </div>

      <!-- Toolbar buttons -->
      <div class="flex items-center gap-1 mb-2">
        
        <!-- Feature 2: Prompts Menu -->
        <div class="relative">
          <button
            @click="togglePromptMenu"
            class="flex items-center gap-0.5 p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 transition-colors"
            :class="{ 'bg-gray-100': showPromptMenu }"
            title="预设提示词"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
          </button>
          
          <!-- Prompt Dropdown -->
          <div v-if="showPromptMenu" class="absolute bottom-full left-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-2 min-w-64 max-w-sm z-50">
            <div class="flex items-center justify-between px-3 pb-2 border-b border-gray-100 dark:border-gray-700 mb-1">
              <span class="text-xs font-semibold text-gray-500">提示词</span>
              <div class="flex gap-1">
                <button v-if="isEditingPrompts" @click="addNewPrompt" class="p-1 text-primary-700 hover:bg-primary-50 rounded transition-colors" title="新增提示词">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                </button>
                <button @click="isEditingPrompts ? savePrompts() : toggleEditPrompts()" class="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors" :title="isEditingPrompts ? '保存' : '编辑'">
                  <svg v-if="isEditingPrompts" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                </button>
              </div>
            </div>
            
            <div class="max-h-60 overflow-y-auto">
              <div v-if="isEditingPrompts" class="px-2 space-y-1">
                <div v-for="(prompt, index) in userPrompts" :key="prompt.id" class="flex items-center gap-1">
                  <input v-model="prompt.text" type="text" class="flex-1 text-xs border border-gray-200 rounded px-2 py-1.5 focus:border-primary-500 outline-none" placeholder="输入提示词..." />
                  <button @click="removePrompt(index)" class="p-1 text-gray-400 hover:text-red-500"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
                </div>
              </div>
              <div v-else>
                 <button
                  v-for="prompt in userPrompts"
                  :key="prompt.id"
                  @click="handlePromptClick(prompt.text)"
                  class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-[#3e3e42] truncate"
                  :title="prompt.text"
                >
                  {{ prompt.text }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- @ Button -->
        <div class="relative">
          <button @click="toggleAtMenu" class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors text-sm font-medium" :class="{ 'bg-gray-100 text-gray-700': showAtMenu }" title="插入引用">@</button>
          <div v-if="showAtMenu" class="absolute bottom-full left-0 mb-1 bg-gray-800/90 rounded-lg py-1 min-w-36 z-50">
            <div class="relative">
              <button @click="handleKeywordClick" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center justify-between"><span>本文关键词</span><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg></button>
              <div v-if="showKeywordSubmenu" class="absolute left-full top-0 ml-1 bg-gray-800/90 rounded-lg py-1 min-w-32">
                <button @click="selectFrameMode" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center gap-2">框选模式</button>
                <div class="border-t border-gray-600 my-1"></div>
                <div class="px-2 py-1 text-xs text-gray-400">已建立索引</div>
                <button v-for="kw in keywordIndexes" :key="kw.id" @click="selectKeywordIndex(kw)" class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-gray-700/50">{{ kw.label }}</button>
              </div>
            </div>
            <button class="w-full text-left px-3 py-2 text-sm text-gray-400 cursor-not-allowed">已读论文</button>
          </div>
        </div>

        <!-- Attachment -->
        <button @click="triggerFileInput" class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors" title="添加文件">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
        </button>
        <input ref="fileInput" type="file" multiple class="hidden" @change="handleFileSelect" />

        <!-- Chat Mode Toggle Button -->
        <button 
          @click="toggleChatMode" 
          class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          :title="chatMode === 'agent' ? '当前: Agent 模式 (点击切换到简单聊天)' : '当前: 简单聊天模式 (点击切换到 Agent )'"
        >
          <svg v-if="chatMode === 'agent'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </button>

        <!-- Feature 3: Model Selector with Custom Models -->
        <div class="relative ml-auto">
          <button @click="toggleModelMenu" class="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors text-xs" :class="{ 'bg-gray-100 dark:bg-gray-700': showModelMenu }">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
            <span class="max-w-24 truncate">{{ selectedModel }}</span>
            <svg class="w-3 h-3 transition-transform" :class="{ 'rotate-180': showModelMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
          </button>
          <div v-if="showModelMenu" class="absolute bottom-full right-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-1 min-w-36 max-w-48 z-50">
            <button @click="selectModel('README Fusion')" class="w-full text-left px-2.5 py-2 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 transition-colors" :class="{ 'bg-gray-400/50 dark:bg-gray-600/50': selectedModel === 'README Fusion' }">README Fusion</button>
            
            <!-- Custom Models Section -->
            <template v-if="customModels.length > 0">
              <div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
              <div v-for="model in customModels" :key="model.id" class="relative group">
                <button @click="selectModel(model.name)" class="w-full text-left px-2.5 py-2 pr-7 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 transition-colors truncate" :class="{ 'bg-gray-400/50 dark:bg-gray-600/50': selectedModel === model.name }">
                  {{ model.name }}
                </button>
                <button @click="deleteCustomModel(model.id, $event)" class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 opacity-0 group-hover:opacity-100 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-all"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
              </div>
            </template>
            
            <div class="border-t border-gray-200 dark:border-gray-600 my-1"></div>
            <button @click="openCustomModelModal" class="w-full text-left px-2.5 py-2 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
              + 添加自定义模型
            </button>
          </div>
        </div>
      </div>

      <!-- Feature 1: Clean Input Area & Send Button -->
      <div class="flex gap-2 items-end">
        <div class="flex-1 relative">
           <textarea
            v-model="inputMessage"
            placeholder="输入问题..."
            @keyup.enter.exact.prevent="sendMessage()"
            class="w-full px-4 py-3 min-h-[46px] max-h-32 border border-gray-200 dark:border-gray-700 rounded-2xl focus:outline-none focus:border-gray-300 dark:focus:border-gray-600 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-800 text-sm bg-white dark:bg-[#3e3e42] dark:text-gray-200 transition-all duration-200 placeholder:text-gray-400 resize-none overflow-hidden"
            style="field-sizing: content;" 
          ></textarea>
        </div>
        
        <button
          @click="sendMessage()"
          :disabled="!inputMessage.trim() || aiStore.isLoadingChat"
          class="mb-1 p-2.5 rounded-xl transition-all duration-200 flex-shrink-0"
          :class="[
            inputMessage.trim() 
              ? 'bg-gray-900 dark:bg-[#0e639c] text-white hover:bg-gray-800 dark:hover:bg-[#1177bb]' 
              : 'bg-gray-100 dark:bg-[#2d2d30] text-gray-400 dark:text-gray-500 cursor-not-allowed'
          ]"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style>
/* 自定义 Markdown 样式微调，解决 Tailwind Typography 在聊天气泡中的一些间距问题 */
.markdown-body > :first-child {
  margin-top: 0 !important;
}
.markdown-body > :last-child {
  margin-bottom: 0 !important;
}
.markdown-body ul {
  list-style-type: disc;
  padding-left: 1.5em;
}
.markdown-body ol {
  list-style-type: decimal;
  padding-left: 1.5em;
}
/* 调整代码块字体 */
.markdown-body code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
/* 简单的行内代码样式 */
.markdown-body :not(pre) > code {
  background-color: rgba(100, 116, 139, 0.1);
  color: #eb5757;
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
  font-size: 0.875em;
}
.dark .markdown-body :not(pre) > code {
  background-color: rgba(255, 255, 255, 0.1);
  color: #ff7b72;
}

/* 引用标签悬浮效果 */
.citation-ref:hover {
  text-decoration: underline;
}
</style>
