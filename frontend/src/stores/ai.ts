import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Roadmap, Summary, Translation, ChatMessage, AiPanelTab } from '../types'
import { aiApi } from '../api'

export const useAiStore = defineStore('ai', () => {
  const activeTab = ref<AiPanelTab['id']>('roadmap')
  const isPanelCollapsed = ref(false)

  const roadmap = ref<Roadmap | null>(null)
  const summary = ref<Summary | null>(null)
  const currentTranslation = ref<Translation | null>(null)
  const chatMessages = ref<ChatMessage[]>([])

  const isLoadingRoadmap = ref(false)
  const isLoadingSummary = ref(false)
  const isLoadingTranslation = ref(false)
  const isLoadingChat = ref(false)

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
    chatMessages.value.push({
      ...message,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    })
  }

  // 清空聊天消息
  function clearChat() {
    chatMessages.value = []
  }

  // 重置所有数据
  function resetForNewDocument() {
    roadmap.value = null
    summary.value = null
    currentTranslation.value = null
    chatMessages.value = []
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
    resetForNewDocument,
    fetchRoadmap,
  }
})
