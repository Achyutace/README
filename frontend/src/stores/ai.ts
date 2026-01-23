import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { Roadmap, Summary, Translation, ChatMessage, AiPanelTab } from '../types'
import { aiApi, chatSessionApi } from '../api'

// 聊天会话类型
export interface ChatSession {
  id: string
  pdfId: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

export const useAiStore = defineStore('ai', () => {
  const activeTab = ref<AiPanelTab['id']>('roadmap')
  const isPanelHidden = ref(false)

  const roadmap = ref<Roadmap | null>(null)
  const summary = ref<Summary | null>(null)
  const currentTranslation = ref<Translation | null>(null)
  const chatMessages = ref<ChatMessage[]>([])
  
  // 聊天会话管理
  const currentSessionId = ref<string | null>(null)
  const chatSessions = ref<ChatSession[]>([])

  const isLoadingRoadmap = ref(false)
  const isLoadingSummary = ref(false)
  const isLoadingTranslation = ref(false)
  const isLoadingChat = ref(false)

  // 从 sessionStorage 加载聊天会话缓存（关闭浏览器后自动清除）
  function loadSessionsFromStorage() {
    try {
      const stored = sessionStorage.getItem('chatSessions')
      if (stored) {
        const sessions = JSON.parse(stored)
        chatSessions.value = sessions.map((s: any) => ({
          ...s,
          messages: s.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp)
          }))
        }))
      }
    } catch (error) {
      console.error('Failed to load chat sessions from cache:', error)
    }
  }

  // 保存聊天会话到 sessionStorage 缓存
  function saveSessionsToStorage() {
    try {
      sessionStorage.setItem('chatSessions', JSON.stringify(chatSessions.value))
    } catch (error) {
      console.error('Failed to cache chat sessions:', error)
    }
  }

  // 监听会话变化并自动缓存
  watch(chatSessions, () => {
    saveSessionsToStorage()
  }, { deep: true })

  // 从后端加载指定PDF的会话列表
  async function loadSessionsFromBackend(pdfId?: string) {
    try {
      const response = await chatSessionApi.listSessions(pdfId)
      if (response.success && response.sessions) {
        // 将后端数据转换为前端格式
        const backendSessions = response.sessions.map(s => ({
          id: s.id,
          pdfId: s.pdfId || '',
          title: s.title,
          messages: [] as ChatMessage[], // 消息需要单独加载
          createdAt: s.createdAt,
          updatedAt: s.updatedAt
        }))

        if (pdfId) {
          // 如果指定了 pdfId，合并会话（替换该PDF的会话，保留其他PDF的会话）
          const otherSessions = chatSessions.value.filter(s => s.pdfId !== pdfId)
          chatSessions.value = [...backendSessions, ...otherSessions]
        } else {
          chatSessions.value = backendSessions
        }

        console.log(`Loaded ${response.sessions.length} sessions from backend for pdfId: ${pdfId || 'all'}`)
      }
    } catch (error) {
      console.error('Failed to load sessions from backend:', error)
      // 如果后端加载失败，回退到缓存
      loadSessionsFromStorage()
    }
  }

  // 从后端加载指定会话的消息
  async function loadSessionMessagesFromBackend(sessionId: string) {
    try {
      const response = await chatSessionApi.getSessionMessages(sessionId)
      if (response.success && response.messages) {
        // 将后端消息格式转换为前端格式
        const messages: ChatMessage[] = response.messages.map(m => ({
          id: String(m.id),
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: new Date(m.created_time),
          citations: m.citations || []
        }))

        // 更新会话的消息列表
        const session = chatSessions.value.find(s => s.id === sessionId)
        if (session) {
          session.messages = messages
        }

        // 如果是当前会话，更新 chatMessages
        if (currentSessionId.value === sessionId) {
          chatMessages.value = messages
        }

        saveSessionsToStorage()
        console.log(`Loaded ${messages.length} messages for session: ${sessionId}`)
        return messages
      }
    } catch (error) {
      console.error('Failed to load session messages from backend:', error)
    }
    return []
  }

  // 初始化时从缓存加载（后端加载由组件在PDF变化时触发）
  loadSessionsFromStorage()

  const tabs: AiPanelTab[] = [
    { id: 'roadmap', label: 'Roadmap', icon: 'map' },
    { id: 'summary', label: 'Summary', icon: 'document' },
    { id: 'translation', label: 'Translation', icon: 'translate' },
  ]

  // 设置当前激活的tab
  function setActiveTab(tabId: AiPanelTab['id']) {
    activeTab.value = tabId
  }

  // 隐藏/显示面板
  function togglePanel() {
    isPanelHidden.value = !isPanelHidden.value
  }

  // 设置摘要
  function setSummary(newSummary: Summary) {
    summary.value = newSummary
  }

  // 设置翻译
  function setTranslation(translation: Translation) {
    currentTranslation.value = translation
  }

  // 添加聊天消息
  function addChatMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
    const newMessage = {
      ...message,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    }
    chatMessages.value.push(newMessage)
    
    // 如果有当前会话,更新会话的消息列表
    if (currentSessionId.value) {
      const session = chatSessions.value.find(s => s.id === currentSessionId.value)
      if (session) {
        session.messages = [...chatMessages.value]
        session.updatedAt = new Date().toISOString()
        // 更新标题(使用第一条用户消息)
        if (!session.title || session.title === '新对话') {
          const firstUserMsg = session.messages.find(m => m.role === 'user')
          if (firstUserMsg) {
            session.title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '')
          }
        }
      }
    }
  }

  // 清空聊天消息
  function clearChat() {
    chatMessages.value = []
    currentSessionId.value = null
  }
  
  // 创建新会话
  function createNewSession(pdfId: string): string {
    const sessionId = crypto.randomUUID()
    const newSession: ChatSession = {
      id: sessionId,
      pdfId,
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    chatSessions.value.unshift(newSession)
    currentSessionId.value = sessionId
    chatMessages.value = []
    return sessionId
  }
  
  // 加载会话（从后端获取消息）
  async function loadSession(sessionId: string) {
    const session = chatSessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSessionId.value = sessionId

      // 如果本地没有消息，从后端加载
      if (session.messages.length === 0) {
        isLoadingChat.value = true
        try {
          await loadSessionMessagesFromBackend(sessionId)
        } finally {
          isLoadingChat.value = false
        }
      } else {
        chatMessages.value = [...session.messages]
      }
    }
  }
  
  // 获取当前 PDF 的所有会话
  function getSessionsByPdfId(pdfId: string): ChatSession[] {
    return chatSessions.value.filter(s => s.pdfId === pdfId)
  }
  
  // 删除会话
  async function deleteSession(sessionId: string) {
    try {
      // 调用后端 API 删除会话
      const response = await chatSessionApi.deleteSession(sessionId)
      
      if (response.success) {
        // 删除成功后，从本地状态中移除
        const index = chatSessions.value.findIndex(s => s.id === sessionId)
        if (index !== -1) {
          chatSessions.value.splice(index, 1)
          if (currentSessionId.value === sessionId) {
            clearChat()
          }
        }
        // 缓存会通过 watch 自动更新
        console.log(`Session ${sessionId} deleted. ${response.deletedMessages} messages removed.`)
      }
    } catch (error: any) {
      console.error('Failed to delete session:', error)
      
      // 如果后端返回 404（会话不存在），也从本地删除
      if (error?.response?.status === 404) {
        console.warn(`Session ${sessionId} not found in backend, removing from cache`)
        const index = chatSessions.value.findIndex(s => s.id === sessionId)
        if (index !== -1) {
          chatSessions.value.splice(index, 1)
          if (currentSessionId.value === sessionId) {
            clearChat()
          }
        }
      } else {
        throw error
      }
    }
  }

  // 重置所有数据
  function resetForNewDocument() {
    roadmap.value = null
    summary.value = null
    currentTranslation.value = null
    chatMessages.value = []
    currentSessionId.value = null
  }

  // 设置大纲
  function setRoadmap(newRoadmap: Roadmap) {
    roadmap.value = newRoadmap
  }

  // 获取大纲
  async function fetchRoadmap(pdfId: string) {
    if (roadmap.value) return // Return cached version if exists

    isLoadingRoadmap.value = true
    try {
      const data = await aiApi.generateRoadmap(pdfId)
      // Ensure nodes have positions for Vue Flow
      const processedRoadmap = layoutNodes(data)
      setRoadmap(processedRoadmap)
    } catch (error) {
      console.error('Error fetching roadmap:', error)
    } finally {
      isLoadingRoadmap.value = false
    }
  }

  // Simple auto-layout helper (in a real app, use dagre or elkjs)
  function layoutNodes(data: Roadmap): Roadmap {
    // Check if positions already exist
    if (data.nodes.some(n => n.position && (n.position.x !== 0 || n.position.y !== 0))) {
        return data;
    }

    const nodes = data.nodes.map((node, index) => ({
      ...node,
      position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 150 },
      data: node.data // preserve data
    }))
    return { ...data, nodes }
  }

  return {
    activeTab,
    isPanelHidden,
    roadmap,
    summary,
    currentTranslation,
    chatMessages,
    currentSessionId,
    chatSessions,
    isLoadingRoadmap,
    isLoadingSummary,
    isLoadingTranslation,
    isLoadingChat,
    tabs,
    setActiveTab,
    togglePanel,
    setRoadmap,
    setSummary,
    setTranslation,
    addChatMessage,
    clearChat,
    createNewSession,
    loadSession,
    loadSessionsFromBackend,
    loadSessionMessagesFromBackend,
    getSessionsByPdfId,
    deleteSession,
    resetForNewDocument,
    fetchRoadmap,
  }
})
