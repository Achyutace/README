/*
----------------------------------------------------------------------
                          上传PDF管理（AI 相关状态与会话）
----------------------------------------------------------------------

  说明：
  - 本文件使用 Pinia 定义了一个名为 `ai` 的 store，用于管理与 PDF 相关的 AI 功能：
    大纲（roadmap）、摘要（summary）、翻译（translation）以及基于 PDF 的聊天会话（chat sessions）。
  - 主要职责包括：缓存会话（sessionStorage）、与后端同步会话列表/消息、管理当前会话状态、以及调用 AI 接口生成大纲。
*/

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { Roadmap, Summary, Translation, ChatMessage, AiPanelTab } from '../types'
import { aiApi, chatSessionApi } from '../api'

// -----------------------------
// 会话类型定义（前端使用的格式）
// -----------------------------
// 注：后端返回的数据会被转换为此结构以便前端统一处理
export interface ChatSession {
  id: string            // 会话唯一 ID（优先使用后端 id，离线时前端可生成临时 id）
  pdfId: string         // 关联的 PDF ID，用于按文档分组会话
  title: string         // 会话标题（通常使用首条用户消息的前 30 字）
  messages: ChatMessage[] // 消息数组（ChatMessage 在 types 中定义，包含 role/content/timestamp 等）
  createdAt: string     // 会话创建时间（ISO 字符串）
  updatedAt: string     // 会话更新时间（ISO 字符串）
}

// -----------------------------
// Pinia store: useAiStore
// -----------------------------
export const useAiStore = defineStore('ai', () => {
  // UI 状态
  const activeTab = ref<AiPanelTab['id']>('roadmap') // 当前激活面板（roadmap/summary/translation）
  const isPanelHidden = ref(false) // 面板是否被折叠隐藏

  // 数据状态
  const roadmap = ref<Roadmap | null>(null) // 当前 PDF 的大纲（缓存）
  const summary = ref<Summary | null>(null) // 文档摘要
  const currentTranslation = ref<Translation | null>(null) // 当前选中的翻译结果
  const chatMessages = ref<ChatMessage[]>([]) // 当前会话的消息（显示在聊天窗口）

  // 会话管理
  const currentSessionId = ref<string | null>(localStorage.getItem('readme_current_session') || null) // 当前激活的会话 ID（null 表示未选择会话）
  const chatSessions = ref<ChatSession[]>([]) // 所有会话（可能包含来自不同 PDF 的会话）

  // 加载状态标志，用于显示 loading 指示器
  const isLoadingRoadmap = ref(false)
  const isLoadingSummary = ref(false)
  const isLoadingTranslation = ref(false)
  const isLoadingChat = ref(false)

  // -----------------------------
  // 本地缓存（只有极轻量状态 ID）相关逻辑
  // -----------------------------

  // 监听当前会话 ID 的变化并持久化至 localStorage，以保障刷新不断代
  watch(currentSessionId, (newId) => {
    if (newId) {
      localStorage.setItem('readme_current_session', newId)
    } else {
      localStorage.removeItem('readme_current_session')
    }
  })

  // -----------------------------
  // 与后端交互：加载会话列表
  // -----------------------------
  // 可传入 pdfId 指定只加载某个 PDF 的会话；否则加载后端返回的所有会话
  async function loadSessionsFromBackend(pdfId?: string) {
    try {
      const response = await chatSessionApi.listSessions(pdfId)
      if (response.success && response.sessions) {
        // 将后端数据转换为前端 ChatSession 格式（消息列表单独加载，避免一次性拉取大量消息）
        const backendSessions = response.sessions.map(s => ({
          id: s.id,
          pdfId: s.pdfId || '',
          title: s.title,
          messages: [] as ChatMessage[], // 延迟加载消息
          createdAt: s.createdAt,
          updatedAt: s.updatedAt
        }))

        if (pdfId) {
          // 如果指定了 pdfId，则用后端返回的该 PDF 的会话替换本地同一 pdfId 的会话，保留其它 PDF 的会话
          const otherSessions = chatSessions.value.filter(s => s.pdfId !== pdfId)
          chatSessions.value = [...backendSessions, ...otherSessions]
        } else {
          // 否则直接使用后端返回的会话列表
          chatSessions.value = backendSessions
        }

        // 校验：如果当前 currentSessionId 不在新列表中，说明该会话已被后端删除，重置状态
        if (currentSessionId.value) {
          const stillExists = chatSessions.value.some(s => s.id === currentSessionId.value)
          if (!stillExists) {
            console.warn(`[AI Store] Session ${currentSessionId.value} no longer exists on backend. Resetting.`)
            clearChat()
          }
        }

        console.log(`Loaded ${response.sessions.length} sessions from backend for pdfId: ${pdfId || 'all'}`)
      }
    } catch (error) {
      console.error('Failed to load sessions from backend:', error)
      // 后端不可达时保留本地缓存数据，不做清除（离线降级）
    }
  }

  // -----------------------------
  // 与后端交互：加载指定会话的消息列表
  // -----------------------------
  async function loadSessionMessagesFromBackend(sessionId: string) {
    try {
      const response = await chatSessionApi.getSessionMessages(sessionId)
      if (response.success && response.messages) {
        // 转换后端消息为前端 ChatMessage 格式并把时间戳转为 Date
        const messages: ChatMessage[] = response.messages.map(m => ({
          id: String(m.id),
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: new Date(m.created_time),
          citations: m.citations || []
        }))

        // 更新对应会话的 messages
        const session = chatSessions.value.find(s => s.id === sessionId)
        if (session) {
          session.messages = messages
        }

        // 如果当前正在查看该会话，则更新 chatMessages（聊天窗口显示）
        if (currentSessionId.value === sessionId) {
          chatMessages.value = messages
        }

        // 去掉了本地粗放的 json 保存，只用负责内存更新和呈现
        console.log(`Loaded ${messages.length} messages for session: ${sessionId}`)
        return messages
      }
    } catch (error) {
      console.error('Failed to load session messages from backend:', error)
    }
    return []
  }

  // -----------------------------
  // 面板标签定义（用于 UI）
  // -----------------------------
  const tabs: AiPanelTab[] = [
    { id: 'roadmap', label: 'Roadmap', icon: 'map' },
    { id: 'summary', label: 'Summary', icon: 'document' },
    { id: 'translation', label: 'Translation', icon: 'translate' },
  ]

  // 切换当前激活的 tab
  function setActiveTab(tabId: AiPanelTab['id']) {
    activeTab.value = tabId
  }

  // 折叠/展开侧边面板
  function togglePanel() {
    isPanelHidden.value = !isPanelHidden.value
  }

  // 更新摘要
  function setSummary(newSummary: Summary) {
    summary.value = newSummary
  }

  // 更新翻译结果
  function setTranslation(translation: Translation) {
    currentTranslation.value = translation
  }

  // -----------------------------
  // 聊天消息操作
  // -----------------------------
  // 添加一条消息到当前聊天（不含 id/timestamp -- 由此函数生成）
  function addChatMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
    const newMessage = {
      ...message,
      id: crypto.randomUUID(),      // 使用 Web Crypto API 生成唯一 id
      timestamp: new Date(),        // 生成消息时间戳
    }
    chatMessages.value.push(newMessage)

    // 如果当前有会话，更新该会话的消息数组并刷新 updatedAt
    if (currentSessionId.value) {
      const session = chatSessions.value.find(s => s.id === currentSessionId.value)
      if (session) {
        session.messages = [...chatMessages.value]
        session.updatedAt = new Date().toISOString()
        // 如果会话标题为空或默认为 '新对话'，则用第一条用户消息生成简短标题
        if (!session.title || session.title === '新对话') {
          const firstUserMsg = session.messages.find(m => m.role === 'user')
          if (firstUserMsg) {
            session.title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '')
          }
        }
      }
    }
  }

  // 清空当前聊天窗口并取消选中会话
  function clearChat() {
    chatMessages.value = []
    currentSessionId.value = null
  }

  // -----------------------------
  // 会话创建 / 加载 / 删除
  // -----------------------------
  // 创建新会话：优先调用后端创建，会返回后端 sessionId；若失败则降级为前端生成临时 id
  async function createNewSession(pdfId: string): Promise<string> {
    try {
      // 请求后端创建会话
      const data = await chatSessionApi.createSession()

      const newSession: ChatSession = {
        id: data.sessionId, // 使用后端返回的 ID
        pdfId,
        title: data.title || '新对话',
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }

      // 将新会话插入到本地会话列表（靠前显示）并设置为当前会话
      chatSessions.value.unshift(newSession)
      currentSessionId.value = data.sessionId!
      chatMessages.value = []

      // 发送全局跨标签广播，通知更新会话列表
      import('../utils/broadcast').then(({ broadcastSync }) => {
        broadcastSync('RELOAD_SESSIONS', pdfId)
      })

      return data.sessionId!
    } catch (error) {
      console.error('Failed to create session on backend:', error)
      throw error // 移除了“向后兼容”的伪离线建立功能，直接抛错
    }
  }

  // 加载某个会话：如果本地没有消息，则从后端拉取；否则直接使用本地消息
  async function loadSession(sessionId: string) {
    const session = chatSessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSessionId.value = sessionId

      // 如果没有本地消息，则从后端加载（并显示 loading）
      if (session.messages.length === 0) {
        isLoadingChat.value = true
        try {
          await loadSessionMessagesFromBackend(sessionId)
        } finally {
          isLoadingChat.value = false
        }
      } else {
        // 有本地消息则直接赋值给 chatMessages（更新界面）
        chatMessages.value = [...session.messages]
      }
    } else {
      // 会话在本地列表中不存在（可能后端已删除但本地 ID 仍残留）
      console.warn(`[AI Store] Session ${sessionId} not found in local cache. Clearing stale session ID.`)
      // 清空残留的脏 ID，防止后续发送消息时带上无效 sessionId
      currentSessionId.value = null
      chatMessages.value = []
    }
  }

  // 根据 pdfId 筛选出该文档的所有会话
  function getSessionsByPdfId(pdfId: string): ChatSession[] {
    return chatSessions.value.filter(s => s.pdfId === pdfId)
  }

  // 删除会话：调用后端接口删除，同时从本地移除；若后端返回 404（会话不存在）也会本地删除
  async function deleteSession(sessionId: string) {
    try {
      const response = await chatSessionApi.deleteSession(sessionId)

      if (response.success) {
        const index = chatSessions.value.findIndex(s => s.id === sessionId)
        const sessionToRemove = chatSessions.value[index]
        if (index !== -1 && sessionToRemove) {
          const pdfId = sessionToRemove.pdfId
          chatSessions.value.splice(index, 1)
          if (currentSessionId.value === sessionId) {
            clearChat()
          }

          import('../utils/broadcast').then(({ broadcastSync }) => {
            broadcastSync('RELOAD_SESSIONS', pdfId)
          })
        }
        console.log(`Session ${sessionId} deleted. ${response.deletedMessages} messages removed.`)
      }
    } catch (error: any) {
      console.error('Failed to delete session:', error)
      throw error
    }
  }

  // -----------------------------
  // 文档切换 / 重置
  // -----------------------------
  // 当加载新文档时需要重置与上一个文档相关的状态
  function resetForNewDocument() {
    roadmap.value = null
    summary.value = null
    currentTranslation.value = null
    chatMessages.value = []
    currentSessionId.value = null
  }

  // 更新 roadmap
  function setRoadmap(newRoadmap: Roadmap) {
    roadmap.value = newRoadmap
  }

  // -----------------------------
  // 与 AI 接口相关：生成并缓存大纲（roadmap）
  // -----------------------------
  async function fetchRoadmap(pdfId: string) {
    // 已经缓存则直接返回，避免重复请求
    if (roadmap.value) return

    isLoadingRoadmap.value = true
    try {
      const data = await aiApi.generateRoadmap(pdfId)
      // 为了在 Vue Flow 中显示，需要确保每个节点有 position；这里提供简单自动布局
      const processedRoadmap = layoutNodes(data)
      setRoadmap(processedRoadmap)
    } catch (error) {
      console.error('Error fetching roadmap:', error)
    } finally {
      isLoadingRoadmap.value = false
    }
  }

  // 简单的自动布局函数：为没有 position 的节点生成网格布局
  // 提示：真实项目中建议使用更专业的布局库（dagre/elkjs）以获得更好的可视化效果
  function layoutNodes(data: Roadmap): Roadmap {
    // 如果节点已经有明确 position，则保留原样
    if (data.nodes.some(n => n.position && (n.position.x !== 0 || n.position.y !== 0))) {
      return data;
    }

    const nodes = data.nodes.map((node, index) => ({
      ...node,
      position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 150 },
      data: node.data // 保持原有 data
    }))
    return { ...data, nodes }
  }

  // -----------------------------
  // 事件监听：跨标签页广播同步
  // -----------------------------
  import('../utils/broadcast').then(({ syncChannel }) => {
    syncChannel.addEventListener('message', (event) => {
      const { type, payload } = event.data

      switch (type) {
        case 'RELOAD_SESSIONS':
          // 如果广播发来了 pdfId，我们默默地更新对应的后台列表
          if (payload) {
            loadSessionsFromBackend(payload)
          } else {
            loadSessionsFromBackend()
          }
          break
        case 'RELOAD_MESSAGES':
          // 重载当前消息（别人在这个会话里发了消息或者更新）
          if (payload && payload === currentSessionId.value) {
            loadSessionMessagesFromBackend(payload)
          }
          break
      }
    })
  }).catch(e => console.error("Broadcast init failed in AI store", e))

  // -----------------------------
  // 对外暴露的状态与方法
  // -----------------------------
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
