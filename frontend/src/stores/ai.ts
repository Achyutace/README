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
  const isPanelCollapsed = ref(false)

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
  
  // 从 localStorage 加载聊天会话
  function loadSessionsFromStorage() {
    try {
      const stored = localStorage.getItem('chatSessions')
      if (stored) {
        const sessions = JSON.parse(stored)
        // 恢复 Date 对象
        chatSessions.value = sessions.map((s: any) => ({
          ...s,
          createdAt: s.createdAt,
          updatedAt: s.updatedAt,
          messages: s.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp)
          }))
        }))
      }
    } catch (error) {
      console.error('Failed to load chat sessions:', error)
    }
  }
  
  // 保存聊天会话到 localStorage
  function saveSessionsToStorage() {
    try {
      localStorage.setItem('chatSessions', JSON.stringify(chatSessions.value))
    } catch (error) {
      console.error('Failed to save chat sessions:', error)
    }
  }
  
  // 监听会话变化并自动保存
  watch(chatSessions, () => {
    saveSessionsToStorage()
  }, { deep: true })
  
  // 从后端加载会话列表
  async function loadSessionsFromBackend(pdfId?: string) {
    try {
      const response = await chatSessionApi.listSessions(pdfId)
      if (response.success && response.sessions) {
        // 将后端数据转换为前端格式
        chatSessions.value = response.sessions.map(s => ({
          id: s.id,
          pdfId: s.pdfId || '',
          title: s.title,
          messages: [], // 消息需要单独加载
          createdAt: s.createdAt,
          updatedAt: s.updatedAt
        }))
        // 保存到 localStorage
        saveSessionsToStorage()
        console.log(`Loaded ${response.sessions.length} sessions from backend`)
      }
    } catch (error) {
      console.error('Failed to load sessions from backend:', error)
      // 如果后端加载失败，回退到 localStorage
      loadSessionsFromStorage()
    }
  }
  
  // 初始化时优先从后端加载，失败则使用 localStorage
  loadSessionsFromBackend()

  const tabs: AiPanelTab[] = [
    { id: 'roadmap', label: 'Roadmap', icon: 'map' },
    { id: 'summary', label: 'Summary', icon: 'document' },
    { id: 'translation', label: 'Translation', icon: 'translate' },
  ]

  // 设置当前激活的tab
  function setActiveTab(tabId: AiPanelTab['id']) {
    activeTab.value = tabId
  }

  // 折叠/展开面板
  function togglePanel() {
    isPanelCollapsed.value = !isPanelCollapsed.value
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
  
  // 加载会话
  function loadSession(sessionId: string) {
    const session = chatSessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSessionId.value = sessionId
      chatMessages.value = [...session.messages]
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
        // localStorage 会通过 watch 自动更新
        console.log(`Session ${sessionId} deleted. ${response.deletedMessages} messages removed.`)
      }
    } catch (error: any) {
      console.error('Failed to delete session:', error)
      
      // 如果后端返回 404（会话不存在），也从本地删除
      if (error?.response?.status === 404) {
        console.warn(`Session ${sessionId} not found in backend, removing from local storage`)
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
    isPanelCollapsed,
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
    getSessionsByPdfId,
    deleteSession,
    resetForNewDocument,
    fetchRoadmap,
  }
})
