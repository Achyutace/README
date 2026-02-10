/*
----------------------------------------------------------------------
                    翻译面板状态管理（Floating Translation Panels）
----------------------------------------------------------------------
*/
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TranslationPanelState, TranslationPanelInstance } from '../types'
import { useAiStore } from './ai'
import { useLibraryStore } from './library'
import { aiApi } from '../api'

export const useTranslationStore = defineStore('translation', () => {
  const aiStore = useAiStore()
  const libraryStore = useLibraryStore()

  // ---------------------- 状态（State） ----------------------
  
  // 划词翻译/快速翻译状态
  const showTextTranslation = ref(false)
  const isTextTranslating = ref(false)
  const textTranslationResult = ref('')

  // 兼容旧版的单一翻译面板状态（为向后兼容保留）
  const translationPanel = ref<TranslationPanelState>({
    isVisible: false,
    paragraphId: '',
    position: { x: 0, y: 0 },
    translation: '',
    isLoading: false,
    originalText: ''
  })

  // 多窗口翻译面板列表
  const translationPanels = ref<TranslationPanelInstance[]>([])

  // 侧边栏停靠的翻译面板 ID 列表
  const sidebarDockedPanels = ref<string[]>([])

  // 翻译缓存：paragraphId -> translation
  const translationCache = ref<Record<string, string>>({})

  // ---------------------- 动作（Actions） ----------------------

  // ---------------------- 划词翻译功能 ----------------------
  
  // 翻译文本 (Translate Text Selection)
  async function translateText(text: string) {
    showTextTranslation.value = true
    isTextTranslating.value = true
    textTranslationResult.value = ''
    
    try {
      const pdfId = libraryStore.currentDocumentId
      const response = await aiApi.translateText(text, pdfId || undefined)
      
      if (response && response.translatedText) {
         textTranslationResult.value = response.translatedText
         aiStore.setTranslation(response)
      } else {
         textTranslationResult.value = "未能获取翻译结果"
      }
    } catch (error) {
      console.error('Translation failed:', error)
      textTranslationResult.value = "翻译请求失败，请稍后重试。"
    } finally {
      isTextTranslating.value = false
    }
  }

  // 关闭划词翻译面板
  function closeTextTranslation() {
    showTextTranslation.value = false
  }

  // ---------------------- API 包装 ----------------------

  // 翻译段落 (Translate Paragraph)
  async function translateParagraph(paragraphId: string, forceRefresh = false): Promise<string | null> {
    try {
      const pdfId = libraryStore.currentDocumentId
      if (!pdfId) {
        console.warn('No active PDF document found.')
        return null
      }
      
      const result = await aiApi.translateParagraph(pdfId, paragraphId, forceRefresh)
      if (result.success) {
        return result.translation
      } else {
        console.warn('Translation API returned success=false')
        return null
      }
    } catch (error) {
      console.error('Paragraph translation failed:', error)
      return null
    }
  }

  // ---------------------- 翻译面板管理 ----------------------

  // 打开翻译面板（支持多窗口），会检查缓存并将已存在的面板聚焦
  function openTranslationPanel(paragraphId: string, position: { x: number; y: number }, originalText: string) {
    // 先尝试从缓存中获取翻译，若存在则直接使用
    const cached = translationCache.value[paragraphId]
    
    // 若已存在同一段落的翻译面板，则把它移到数组末尾以实现聚焦效果
    const existingPanel = translationPanels.value.find(p => p.paragraphId === paragraphId)
    if (existingPanel) {
      const index = translationPanels.value.indexOf(existingPanel)
      translationPanels.value.splice(index, 1)
      translationPanels.value.push(existingPanel)
      return
    }
    
    // 创建并初始化一个新的翻译面板实例
    const newPanel: TranslationPanelInstance = {
      id: `tp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      paragraphId,
      position,
      size: { width: 420, height: 280 },
      translation: cached || '',
      isLoading: !cached,
      originalText,
      snapMode: 'none',
      snapTargetParagraphId: null,
      isSidebarDocked: false
    }
    
    translationPanels.value.push(newPanel)
    
    // 同时更新旧版的单一翻译面板状态以保持向后兼容
    translationPanel.value = {
      isVisible: true,
      paragraphId,
      position,
      translation: cached || '',
      isLoading: !cached,
      originalText
    }
  }

  // 关闭旧版的单一翻译面板（仅影响兼容的状态表示）
  function closeTranslationPanel() {
    translationPanel.value.isVisible = false
  }
  
  // 关闭指定 ID 的翻译面板，并处理侧边栏停靠列表
  function closeTranslationPanelById(panelId: string) {
    const index = translationPanels.value.findIndex(p => p.id === panelId)
    if (index !== -1) {
      // 如果该面板在侧边栏停靠列表中，也将其移除
      const sidebarIndex = sidebarDockedPanels.value.indexOf(panelId)
      if (sidebarIndex !== -1) {
        sidebarDockedPanels.value.splice(sidebarIndex, 1)
      }
      translationPanels.value.splice(index, 1)
    }
  }

  // 更新旧版翻译面板的位置（兼容）
  function updateTranslationPanelPosition(position: { x: number; y: number }) {
    translationPanel.value.position = position
  }
  
  // 更新指定面板的位置（多窗口）
  function updatePanelPosition(panelId: string, position: { x: number; y: number }) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.position = position
    }
  }
  
  // 更新指定面板尺寸
  function updatePanelSize(panelId: string, size: { width: number; height: number }) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.size = size
    }
  }
  
  // 设置面板的吸附模式（none / paragraph / sidebar），并维护侧边栏停靠列表
  function setPanelSnapMode(panelId: string, mode: 'none' | 'paragraph' | 'sidebar', targetParagraphId?: string) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.snapMode = mode
      panel.snapTargetParagraphId = targetParagraphId || null
      panel.isSidebarDocked = mode === 'sidebar'
      
      // 管理侧边栏停靠数组，避免重复或残留条目
      const sidebarIndex = sidebarDockedPanels.value.indexOf(panelId)
      if (mode === 'sidebar' && sidebarIndex === -1) {
        sidebarDockedPanels.value.push(panelId)
      } else if (mode !== 'sidebar' && sidebarIndex !== -1) {
        sidebarDockedPanels.value.splice(sidebarIndex, 1)
      }
    }
  }

  // 设置翻译结果并更新缓存与所有相关面板状态
  function setTranslation(paragraphId: string, translation: string) {
    translationCache.value[paragraphId] = translation
    
    // 如果旧版面板正在显示相同段落，则同步更新
    if (translationPanel.value.paragraphId === paragraphId) {
      translationPanel.value.translation = translation
      translationPanel.value.isLoading = false
    }
    
    // 更新所有匹配的多窗口翻译面板
    translationPanels.value.forEach(panel => {
      if (panel.paragraphId === paragraphId) {
        panel.translation = translation
        panel.isLoading = false
      }
    })
  }

  // 设置旧版翻译面板的加载状态
  function setTranslationLoading(loading: boolean) {
    translationPanel.value.isLoading = loading
  }
  
  // 设置指定多窗口面板的加载状态
  function setPanelLoading(panelId: string, loading: boolean) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.isLoading = loading
    }
  }
  
  // 将指定面板移动到数组末尾，从而在 UI 层表现为置顶/聚焦
  function bringPanelToFront(panelId: string) {
    const index = translationPanels.value.findIndex(p => p.id === panelId)
    if (index !== -1 && index !== translationPanels.value.length - 1) {
      const panel = translationPanels.value.splice(index, 1)[0]
      if (panel) {
        translationPanels.value.push(panel)
      }
    }
  }
  
  // 关闭所有面板
  function closeAllPanels() {
    translationPanels.value = []
    sidebarDockedPanels.value = []
    closeTranslationPanel()
  }

  return {
    // State
    translationPanel,
    translationPanels,
    sidebarDockedPanels,
    translationCache,
    showTextTranslation,
    isTextTranslating,
    textTranslationResult,
    
    // Actions
    translateText,
    closeTextTranslation,
    translateParagraph,
    openTranslationPanel,
    closeTranslationPanel,
    closeTranslationPanelById,
    updateTranslationPanelPosition,
    updatePanelPosition,
    updatePanelSize,
    setPanelSnapMode,
    setTranslation,
    setTranslationLoading,
    setPanelLoading,
    bringPanelToFront,
    closeAllPanels
  }
})
