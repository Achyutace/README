<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、Markdown 支持、代码高亮及应用 store/API
import { ref, computed, watch, onMounted, nextTick } from 'vue'  // 导入 Vue 的响应式 API 和生命周期钩子
import { useChatStore } from '../../stores/chat'
import { usePanelStore } from '../../stores/panel'  // 导入 AI 相关的状态管理 store
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
const chatStore = useChatStore()
const panelStore = usePanelStore()  // 创建 AI store 实例
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
    await chatStore.createNewSession(pdfId)
  }
  showHistoryPanel.value = false
}
const loadChatSession = async (sessionId: string) => {
  await chatStore.loadSession(sessionId)
  showHistoryPanel.value = false  // 关闭历史面板
}

const deleteChatSession = async (sessionId: string, event: Event) => {  // 删除聊天会话
  event.stopPropagation()  // 阻止事件冒泡
  if (confirm('确定要删除这个对话吗？')) {  // 确认删除
    try {
      await chatStore.deleteSession(sessionId)
    } catch (error) {
      console.error('删除会话失败:', error)  // 记录错误
    }
  }
}

const currentPdfSessions = computed(() => {  // 获取当前 PDF 的会话列表（computed 缓存）
  const pdfId = libraryStore.currentDocumentId  // 获取当前 PDF ID
  if (!pdfId) return []  // 如果没有 PDF ID，返回空数组
  return chatStore.getSessionsByPdfId(pdfId)
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
  const message = chatStore.chatMessages[index]
  if (!message || chatStore.isLoadingChat) return
  
  let targetContent = message.content
  let historyIndex = index
  
  // 如果点的是 AI 消息的重试，说明需要“重新生成”，即重发上一条用户消息
  if (message.role === 'assistant' && index > 0) {
    const prevMsg = chatStore.chatMessages[index - 1]
    if (prevMsg && prevMsg.role === 'user') {
      targetContent = prevMsg.content
      historyIndex = index - 1
    }
  }

  // 构造历史：取历史点之前的所有消息
  const history = chatStore.chatMessages.slice(0, historyIndex).map(m => ({
    role: m.role,
    content: m.content
  }))

  await executeSendMessage(targetContent, history, { resendFromIndex: index })
}

const handleResendEdited = async (index: number, newContent: string) => {
  if (chatStore.isLoadingChat) return

  // 构造历史
  const history = chatStore.chatMessages.slice(0, index).map(m => ({
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
    // 如果是重发且不是编辑，我们可能需要特殊处理
    // 根据用户要求，前端保留旧信息（软裁减）
    
    let pruneFromId: string | undefined = undefined
    if (meta?.resendFromIndex !== undefined) {
      const originalMsg = chatStore.chatMessages[meta.resendFromIndex]
      if (originalMsg && originalMsg.id && !originalMsg.id.includes('-')) {
        /**
         * 为什么使用 id >= pruneFromId 是合理正确的？
         * 1. 确定性：数据库 ID 在单表自增序列中是严格单调递增的，它比 timestamp 更能代表物理插入顺序。
         * 2. 裁减范围：当用户重发消息 i 时，意味着他想“回滚”到 i 之前的状态并开启新分支。
         *    删除 id >= id(i) 的所有记录，可以精确清除该位置及其之后的所有数据库污染，且不会误删在该位置之前的并发消息。
         */
        pruneFromId = originalMsg.id
      }
    }

    chatStore.addChatMessage({
      role: 'user',
      content: content,
      meta: meta
    })

    chatStore.isLoadingChat = true

    try {
      if (!libraryStore.currentDocumentId) {
        alert("找不到有效文档，请先在左侧选择 PDF。")
        chatStore.isLoadingChat = false
        return
      }

      // 确保如果是临时会话，先在后端真实创建一个
      const realSessionId = await chatStore.ensureRealSession(libraryStore.currentDocumentId);
      
      // 调用 API，传入 historyOverride 和 pruneFromId
      const data = await chatSessionApi.sendMessage(
        realSessionId,
        content,
        libraryStore.currentDocumentId,
        chatMode.value,
        selectedModel.value,
        apiBase,
        apiKey,
        historyOverride,
        pruneFromId
      )
    
    chatStore.addChatMessage({
      role: 'assistant',
      content: data.response,
      citations: data.citations || []
    })

    nextTick(() => {
      messageListRef.value?.scrollToBottom()
    })
    
  } catch (error: any) {
    console.error('发送消息异常:', error)
    chatStore.addChatMessage({
      role: 'assistant',
      content: '抱歉，网络请求失败，请检查后端服务或密钥配置。',
      citations: []
    })
  } finally {
    chatStore.isLoadingChat = false
  }
}

// --- Selection Logic ---
const handleToggleSelectionMode = () => {
  panelStore.toggleSelectionMode()
}

const handleToggleMessageSelection = (id: string) => {
  panelStore.toggleMessageSelection(id)
}

const handleCopySelected = () => {
  const json = chatStore.copySelectedAsJson(panelStore.selectedMessageIds)
  if (json && json !== '[]') {
    navigator.clipboard.writeText(json)
    alert('已复制选中内容到剪贴板')
    panelStore.selectionMode = false
    panelStore.selectedMessageIds.clear()
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
    chatStore.clearChat()
    await chatStore.loadSessionsFromBackend(pdfId)
    
    // 自动加载该文档最近的会话或者创建一个新会话
    const sessions = chatStore.getSessionsByPdfId(pdfId)
    const firstSession = sessions[0]
    if (firstSession) {
      await chatStore.loadSession(firstSession.id)
    } else {
      await chatStore.createNewSession(pdfId)
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
      :currentSessionId="chatStore.currentSessionId"
      @close="showHistoryPanel = false"
      @load-session="loadChatSession"
      @delete-session="deleteChatSession"
    />

    <div class="flex-1 flex flex-col relative w-full h-full overflow-hidden">
        <ChatMessageList
          ref="messageListRef"
          :messages="chatStore.chatMessages"
          :isLoadingContent="chatStore.isLoadingChat"
          :selectionMode="panelStore.selectionMode"
          :selectedIds="panelStore.selectedMessageIds"
          @resend="handleResend"
          @resend-edited="handleResendEdited"
          @toggle-selection="handleToggleMessageSelection"
        />

        <!-- Selection Mode Toolbar (Floating) -->
        <div 
          v-if="panelStore.selectionMode" 
          class="absolute bottom-24 left-1/2 -translate-x-1/2 z-50 px-4 py-1.5 bg-blue-50/40 dark:bg-slate-900/40 backdrop-blur-md border border-blue-100/50 dark:border-slate-700 rounded-lg shadow-none flex items-center gap-3 min-w-max transition-all duration-300"
        >
          <span class="text-xs text-slate-600 dark:text-slate-300 whitespace-nowrap">
            已选择 {{ panelStore.selectedMessageIds.size }} 条
          </span>
          <div class="h-3 w-[1px] bg-blue-200/50 dark:bg-slate-700/50"></div>
          <div class="flex gap-1 items-center">
            <button 
              @click="panelStore.selectionMode = false; panelStore.selectedMessageIds.clear()"
              class="px-2 py-0.5 text-xs text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors whitespace-nowrap"
            >取消</button>
            <button 
              @click="handleCopySelected"
              :disabled="panelStore.selectedMessageIds.size === 0"
              class="px-3 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed rounded-md transition-all active:scale-95 whitespace-nowrap"
            >复制为 JSON</button>
          </div>
        </div>

        <ChatInputArea
          :isLoadingContent="chatStore.isLoadingChat"
          :chatMode="chatMode"
          :customModels="customModels"
          :selectedModel="selectedModel"
          :selectedText="pdfStore.selectedText"
          :selectionMode="panelStore.selectionMode"
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
