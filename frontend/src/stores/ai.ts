import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Keyword, Summary, Translation, ChatMessage, AiPanelTab } from '../types'

export const useAiStore = defineStore('ai', () => {
  const activeTab = ref<AiPanelTab['id']>('summary')
  const isPanelCollapsed = ref(false)

  const keywords = ref<Keyword[]>([])
  const summary = ref<Summary | null>(null)
  const currentTranslation = ref<Translation | null>(null)
  const chatMessages = ref<ChatMessage[]>([])

  const isLoadingKeywords = ref(false)
  const isLoadingSummary = ref(false)
  const isLoadingTranslation = ref(false)
  const isLoadingChat = ref(false)

  const tabs: AiPanelTab[] = [
    { id: 'keywords', label: '关键词', icon: 'tag' },
    { id: 'summary', label: '摘要', icon: 'document' },
    { id: 'translation', label: '翻译', icon: 'translate' },
    { id: 'chat', label: '对话', icon: 'chat' },
  ]

  function setActiveTab(tabId: AiPanelTab['id']) {
    activeTab.value = tabId
  }

  function togglePanel() {
    isPanelCollapsed.value = !isPanelCollapsed.value
  }

  function setKeywords(newKeywords: Keyword[]) {
    keywords.value = newKeywords
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
    keywords.value = []
    summary.value = null
    currentTranslation.value = null
    chatMessages.value = []
  }

  return {
    activeTab,
    isPanelCollapsed,
    keywords,
    summary,
    currentTranslation,
    chatMessages,
    isLoadingKeywords,
    isLoadingSummary,
    isLoadingTranslation,
    isLoadingChat,
    tabs,
    setActiveTab,
    togglePanel,
    setKeywords,
    setSummary,
    setTranslation,
    addChatMessage,
    clearChat,
    resetForNewDocument,
  }
})
