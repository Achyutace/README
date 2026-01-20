import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Roadmap, Summary, Translation, ChatMessage, AiPanelTab } from '../types'

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
    { id: 'chat', label: 'Chat', icon: 'chat' },
  ]

  function setActiveTab(tabId: AiPanelTab['id']) {
    activeTab.value = tabId
  }

  function togglePanel() {
    isPanelCollapsed.value = !isPanelCollapsed.value
  }

  function setSummary(newSummary: Summary) {
    summary.value = newSummary
  }

  function setTranslation(translation: Translation) {
    currentTranslation.value = translation
  }

  function addChatMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
    chatMessages.value.push({
      ...message,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    })
  }

  function clearChat() {
    chatMessages.value = []
  }

  function resetForNewDocument() {
    roadmap.value = null
    summary.value = null
    currentTranslation.value = null
    chatMessages.value = []
  }

  function setRoadmap(newRoadmap: Roadmap) {
    roadmap.value = newRoadmap
  }

  async function fetchRoadmap(pdfId: string) {
    if (roadmap.value) return // Return cached version if exists

    isLoadingRoadmap.value = true
    try {
      const response = await fetch('http://localhost:5000/api/ai/roadmap', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdfId }),
      })
      
      if (!response.ok) throw new Error('Failed to fetch roadmap')
      
      const data = await response.json()
      // Ensure nodes have positions for Vue Flow
      const processedRoadmap = layoutNodes(data.roadmap)
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
