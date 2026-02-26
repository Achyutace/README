<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、Markdown 支持、代码高亮及应用 store/API
import { ref, computed, watch, onMounted, nextTick } from 'vue'  // 导入 Vue 的响应式 API 和生命周期钩子
import { useAiStore } from '../../stores/ai'  // 导入 AI 相关的状态管理 store
import { useLibraryStore } from '../../stores/library'  // 导入库相关的状态管理 store
import { usePdfStore } from '../../stores/pdf'  // 导入 PDF 相关的状态管理 store
import { chatSessionApi } from '../../api'  // 导入聊天会话 API
import type { CustomModel } from '../../types'  // 导入自定义模型类型
import PinSecurityModal from './PinSecurityModal.vue'
import CustomModelModal from './CustomModelModal.vue'
import ChatHistorySidebar from './ChatHistorySidebar.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatInputArea from './ChatInputArea.vue'

// 初始化各个 store 实例
const aiStore = useAiStore()  // 创建 AI store 实例
const libraryStore = useLibraryStore()  // 创建库 store 实例
const pdfStore = usePdfStore()  // 创建 PDF store 实例

// Feature: Custom Models & Model State
const showCustomModelModal = ref(false)
const showPinModal = ref(false)
const selectedModel = ref('README Fusion')
const messageListRef = ref<InstanceType<typeof ChatMessageList> | null>(null)

// --- Feature: Chat Mode Toggle ---
// 聊天模式切换
const chatMode = ref<'agent' | 'simple'>('agent')  // 当前聊天模式，agent 或 simple



// 自定义模型列表
const customModels = ref<CustomModel[]>([])  // 存储自定义模型的响应式数组

// Chat session state
// 聊天会话相关的状态
const showHistoryPanel = ref(false)  // 是否显示历史面板

// (Markdown configuration and Interaction Handlers have been moved to useMarkdownRenderer.ts)

// Lifecycle
onMounted(() => {  // 组件挂载时的生命周期钩子
  // 检查 localStorage 中是否有已加密的自定义模型
  const storedModelsCipher = localStorage.getItem('readme_custom_models_encrypted')
  // 检查热回话内存，看看是否存在已解密的缓存模型 (SessionStorage 保活)
  const sessionModels = sessionStorage.getItem('readme_custom_models_session')

  if (sessionModels) {
    try {
      customModels.value = JSON.parse(sessionModels)
    } catch { /* session 数据损坏 */ }
  } else if (storedModelsCipher) {
    // 存在密文且 Session 里没有，则需要弹出授权
    // 为了防止一进页面就弹授权打扰用户，这里可以设计为按需输入（比如点开发送或要看配置时需要解密）
    // 或者目前为了简单起见并测试加密机制就先弹锁
    showPinModal.value = true
  }
  
  // TODO: 从后端加载用户预设提示词
  // fetchUserPrompts()
})

// --- Chat Mode Handlers ---

const handleCustomModelSave = (modelInfo: { name: string; apiBase: string; apiKey: string }) => {
  const modelToAdd: CustomModel = {  // 创建新模型对象
    id: `custom_${Date.now()}`,  // 生成唯一 ID
    ...modelInfo  // 展开表单数据
  }
  
  customModels.value.push(modelToAdd)  // 添加到模型列表
  
  // 更新完毕，触发保存：此时也需要弹出 PIN 弹窗来设定/生成密钥并写库
  showCustomModelModal.value = false
  showPinModal.value = true  // 交由 PIN 弹窗执行保存加密动作
  selectedModel.value = modelToAdd.name
}

// --- PIN Modal Handlers ---
const handlePinUnlocked = (models: CustomModel[]) => {
  customModels.value = models
  showPinModal.value = false
}

const handlePinCancel = () => {
  showPinModal.value = false
}

// Chat session handlers
const toggleHistoryPanel = () => {  // 切换历史面板显示状态
  showHistoryPanel.value = !showHistoryPanel.value  // 切换显示状态
}

const createNewChat = async () => {  // 创建新聊天
  const pdfId = libraryStore.currentDocumentId  // 获取当前 PDF ID
  if (pdfId) {  // 如果有 PDF ID
    await aiStore.createNewSession(pdfId)  // 创建新会话
  }
  showHistoryPanel.value = false  // 关闭历史面板
}
const loadChatSession = async (sessionId: string) => {  // 加载聊天会话
  await aiStore.loadSession(sessionId)  // 加载指定会话
  showHistoryPanel.value = false  // 关闭历史面板
}

const deleteChatSession = async (sessionId: string, event: Event) => {  // 删除聊天会话
  event.stopPropagation()  // 阻止事件冒泡
  if (confirm('确定要删除这个对话吗？')) {  // 确认删除
    try {
      await aiStore.deleteSession(sessionId)  // 删除会话
    } catch (error) {
      console.error('删除会话失败:', error)  // 记录错误
    }
  }
}

const currentPdfSessions = computed(() => {  // 获取当前 PDF 的会话列表（computed 缓存）
  const pdfId = libraryStore.currentDocumentId  // 获取当前 PDF ID
  if (!pdfId) return []  // 如果没有 PDF ID，返回空数组
  return aiStore.getSessionsByPdfId(pdfId)  // 返回该 PDF 的会话列表
})

// --- Model Change Handler ---
const handleModelChange = (model: string) => {
  selectedModel.value = model
}

// --- Delete Custom Model Handler ---
const handleDeleteModel = (id: string) => {
  const modelToDelete = customModels.value.find(m => m.id === id)
  customModels.value = customModels.value.filter(m => m.id !== id)

  // 1. 更新 session 缓存（本次 tab 内生效）
  sessionStorage.setItem('readme_custom_models_session', JSON.stringify(customModels.value))
  // 2. 清除 localStorage 加密密文，防止下次 session 解锁后已删除的模型复活
  localStorage.removeItem('readme_custom_models_encrypted')

  if (modelToDelete && selectedModel.value === modelToDelete.name) {
    selectedModel.value = 'README Fusion'
  }
}

// --- Toggle Chat Mode Handler ---
const handleToggleMode = () => {
  chatMode.value = chatMode.value === 'agent' ? 'simple' : 'agent'
  console.log('Chat mode switched to:', chatMode.value)
}

// --- Resend Logic ---
const handleResend = async (index: number) => {
  const message = aiStore.chatMessages[index]
  if (!message || aiStore.isLoadingChat) return
  
  // 构造历史：取该消息之前的所有消息
  const history = aiStore.chatMessages.slice(0, index).map(m => ({
    role: m.role,
    content: m.content
  }))

  await executeSendMessage(message.content, history, { resendFromIndex: index })
}

const handleResendEdited = async (index: number, newContent: string) => {
  if (aiStore.isLoadingChat) return

  // 构造历史
  const history = aiStore.chatMessages.slice(0, index).map(m => ({
    role: m.role,
    content: m.content
  }))

  await executeSendMessage(newContent, history, { resendFromIndex: index, edited: true })
}

const executeSendMessage = async (
  content: string, 
  historyOverride?: { role: string; content: string }[],
  meta?: any
) => {
  if (!content) return
  
  // 提取自定义模型配置
  let apiBase: string | undefined = undefined
  let apiKey: string | undefined = undefined
  
  const customModel = customModels.value.find(m => m.name === selectedModel.value)
  if (customModel) {
    apiBase = customModel.apiBase
    apiKey = customModel.apiKey
  }

  // 1. 乐观 UI 更新
  aiStore.addChatMessage({
    role: 'user',
    content: content,
    meta: meta
  })

  aiStore.isLoadingChat = true

  try {
    if (!aiStore.currentSessionId || !libraryStore.currentDocumentId) {
      if (libraryStore.currentDocumentId) {
        await aiStore.createNewSession(libraryStore.currentDocumentId)
      } else {
        alert("找不到有效文档，请先在左侧选择 PDF。")
        aiStore.isLoadingChat = false
        return
      }
    }
    
    // 调用 API，传入 historyOverride
    const data = await chatSessionApi.sendMessage(
      aiStore.currentSessionId!,
      content,
      libraryStore.currentDocumentId,
      chatMode.value,
      selectedModel.value,
      apiBase,
      apiKey,
      historyOverride
    )
    
    aiStore.addChatMessage({
      role: 'assistant',
      content: data.response,
      citations: data.citations || []
    })

    nextTick(() => {
      messageListRef.value?.scrollToBottom()
    })
    
  } catch (error: any) {
    console.error('发送消息异常:', error)
    aiStore.addChatMessage({
      role: 'assistant',
      content: '抱歉，网络请求失败，请检查后端服务或密钥配置。',
      citations: []
    })
  } finally {
    aiStore.isLoadingChat = false
  }
}

// --- Selection Logic ---
const handleToggleSelectionMode = () => {
  aiStore.toggleSelectionMode()
}

const handleToggleMessageSelection = (id: string) => {
  aiStore.toggleMessageSelection(id)
}

const handleCopySelected = () => {
  const json = aiStore.copySelectedAsJson()
  if (json && json !== '[]') {
    navigator.clipboard.writeText(json)
    alert('已复制选中内容到剪贴板')
    aiStore.selectionMode = false
    aiStore.selectedMessageIds.clear()
  }
}

// --- Send Message Logic (Original entry) ---
const handleChatSend = async (payload: { text: string; mode: 'agent' | 'simple'; model: string }) => {
  selectedModel.value = payload.model
  chatMode.value = payload.mode
  await executeSendMessage(payload.text)
}

watch(() => libraryStore.currentDocumentId, async (pdfId) => {  // 监听当前文档 ID 变化
  if (pdfId) {  // 如果有 PDF ID
    aiStore.clearChat()  // 清空聊天
    await aiStore.loadSessionsFromBackend(pdfId)  // 从后端加载会话
    
    // 自动加载该文档最近的会话或者创建一个新会话
    const sessions = aiStore.getSessionsByPdfId(pdfId)
    const firstSession = sessions[0]
    if (firstSession) {
      await aiStore.loadSession(firstSession.id)
    } else {
      await aiStore.createNewSession(pdfId)
    }
  }
}, { immediate: true })  // 立即执行

defineExpose({  // 暴露组件方法
  toggleHistoryPanel,  // 切换历史面板
  createNewChat  // 创建新聊天
})
</script>

<template>
  <div class="h-full flex flex-col relative bg-transparent">
    <!-- ====== PIN 码解锁全局层 ====== -->
    <PinSecurityModal
      v-if="showPinModal"
      :customModels="customModels"
      @unlocked="handlePinUnlocked"
      @cancel="handlePinCancel"
    />

    <!-- Custom Model Modal -->
    <CustomModelModal
      v-if="showCustomModelModal"
      @save="handleCustomModelSave"
      @close="showCustomModelModal = false"
    />

    <!-- History Panel (Overlay) -->
    <ChatHistorySidebar
      v-if="showHistoryPanel"
      :sessions="currentPdfSessions"
      :currentSessionId="aiStore.currentSessionId"
      @close="showHistoryPanel = false"
      @load-session="loadChatSession"
      @delete-session="deleteChatSession"
    />

    <div class="flex-1 flex flex-col relative w-full h-full overflow-hidden">
        <ChatMessageList
          ref="messageListRef"
          :messages="aiStore.chatMessages"
          :isLoadingContent="aiStore.isLoadingChat"
          :selectionMode="aiStore.selectionMode"
          :selectedIds="aiStore.selectedMessageIds"
          @resend="handleResend"
          @resend-edited="handleResendEdited"
          @toggle-selection="handleToggleMessageSelection"
        />

        <!-- Selection Mode Toolbar (Floating) -->
        <div 
          v-if="aiStore.selectionMode" 
          class="absolute bottom-24 left-1/2 -translate-x-1/2 z-50 px-4 py-1.5 bg-blue-50/40 dark:bg-slate-900/40 backdrop-blur-md border border-blue-100/50 dark:border-slate-700 rounded-lg shadow-none flex items-center gap-3 min-w-max transition-all duration-300"
        >
          <span class="text-xs text-slate-600 dark:text-slate-300 whitespace-nowrap">
            已选择 {{ aiStore.selectedMessageIds.size }} 条
          </span>
          <div class="h-3 w-[1px] bg-blue-200/50 dark:bg-slate-700/50"></div>
          <div class="flex gap-1 items-center">
            <button 
              @click="aiStore.selectionMode = false; aiStore.selectedMessageIds.clear()"
              class="px-2 py-0.5 text-xs text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors whitespace-nowrap"
            >取消</button>
            <button 
              @click="handleCopySelected"
              :disabled="aiStore.selectedMessageIds.size === 0"
              class="px-3 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed rounded-md transition-all active:scale-95 whitespace-nowrap"
            >复制为 JSON</button>
          </div>
        </div>

        <ChatInputArea
          :isLoadingContent="aiStore.isLoadingChat"
          :chatMode="chatMode"
          :customModels="customModels"
          :selectedModel="selectedModel"
          :selectedText="pdfStore.selectedText"
          :selectionMode="aiStore.selectionMode"
          @clear-selection="pdfStore.clearSelection()"
          @send="handleChatSend"
          @change-model="handleModelChange"
          @open-model-modal="showCustomModelModal = true"
          @delete-model="handleDeleteModel"
          @toggle-mode="handleToggleMode"
          @toggle-selection-mode="handleToggleSelectionMode"
        />
    </div>
  </div>
</template>

<style>
/* 局部外包样式微调 */
</style>
