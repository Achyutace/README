import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PdfParagraph, TranslationPanelState, TranslationPanelInstance } from '../types'

const DEFAULT_SCALE = 1.6
const HIGHLIGHTS_STORAGE_KEY = 'pdf-highlights'

type NormalizedRect = {
  left: number
  top: number
  width: number
  height: number
}

type Highlight = {
  id: string
  page: number
  rects: NormalizedRect[]
  text: string
  color: string
}

// 存储结构：documentId -> Highlight[]
type HighlightsStorage = Record<string, Highlight[]>

export type { Highlight, NormalizedRect }

export const usePdfStore = defineStore('pdf', () => {
  const currentPdfUrl = ref<string | null>(null)
  const currentDocumentId = ref<string | null>(null) // 当前文档ID
  const currentPage = ref(1)
  const totalPages = ref(0)
  const scale = ref(DEFAULT_SCALE)
  const isLoading = ref(false)

  const autoHighlight = ref(false)
  const autoTranslate = ref(false)
  const imageDescription = ref(false)

  const selectedText = ref<string>('')
  const selectionPosition = ref<{ x: number; y: number } | null>(null)
  const selectionInfo = ref<{ page: number; rects: NormalizedRect[] } | null>(null)

  // 所有文档的高亮存储
  const allHighlights = ref<HighlightsStorage>({})
  // 当前文档的高亮（计算属性）
  const highlights = computed(() => {
    if (!currentDocumentId.value) return []
    return allHighlights.value[currentDocumentId.value] || []
  })

  const highlightColor = ref('#F6E05E') // bright yellow by default
  const selectedHighlight = ref<Highlight | null>(null) // 当前选中的高亮
  const isEditingHighlight = ref(false) // 是否在编辑高亮模式

  // 段落数据管理（所有文档的段落）
  const allParagraphs = ref<Record<string, PdfParagraph[]>>({})
  // 当前文档的段落（计算属性）
  const paragraphs = computed(() => {
    if (!currentDocumentId.value) return []
    return allParagraphs.value[currentDocumentId.value] || []
  })

  // 翻译面板状态（保留向后兼容）
  const translationPanel = ref<TranslationPanelState>({
    isVisible: false,
    paragraphId: '',
    position: { x: 0, y: 0 },
    translation: '',
    isLoading: false,
    originalText: ''
  })

  // 多翻译窗口实例列表
  const translationPanels = ref<TranslationPanelInstance[]>([])

  // 侧边栏停靠的翻译面板ID列表
  const sidebarDockedPanels = ref<string[]>([])

  // 翻译缓存（paragraphId -> translation）
  const translationCache = ref<Record<string, string>>({})

  const scalePercent = computed(() => Math.round(scale.value * 100))

  // 从 localStorage 加载高亮数据
  function loadHighlightsFromStorage() {
    try {
      const stored = localStorage.getItem(HIGHLIGHTS_STORAGE_KEY)
      if (stored) {
        allHighlights.value = JSON.parse(stored)
      }
    } catch (err) {
      console.error('Failed to load highlights from storage:', err)
    }
  }

  // 保存高亮数据到 localStorage
  function saveHighlightsToStorage() {
    try {
      localStorage.setItem(HIGHLIGHTS_STORAGE_KEY, JSON.stringify(allHighlights.value))
    } catch (err) {
      console.error('Failed to save highlights to storage:', err)
    }
  }

  // 初始化时加载
  loadHighlightsFromStorage()

  // 监听高亮变化，自动保存
  watch(allHighlights, () => {
    saveHighlightsToStorage()
  }, { deep: true })

  function setCurrentPdf(url: string, documentId?: string) {
    // 清除选择状态
    clearSelection()
    clearHighlightSelection()

    currentPdfUrl.value = url
    currentDocumentId.value = documentId || null
    currentPage.value = 1
    scale.value = DEFAULT_SCALE
    isLoading.value = true

    // 确保当前文档有高亮数组
    if (documentId && !allHighlights.value[documentId]) {
      allHighlights.value[documentId] = []
    }
  }

  function setTotalPages(pages: number) {
    totalPages.value = pages
    isLoading.value = false
  }

  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages.value) {
      currentPage.value = page
    }
  }

  function nextPage() {
    goToPage(currentPage.value + 1)
  }

  function prevPage() {
    goToPage(currentPage.value - 1)
  }

  function zoomIn() {
    if (scale.value < 3.0) {
      scale.value = Math.min(3.0, scale.value + 0.1)
    }
  }

  function zoomOut() {
    if (scale.value > 0.5) {
      scale.value = Math.max(0.5, scale.value - 0.1)
    }
  }

  function setScale(value: number) {
    scale.value = Math.max(0.5, Math.min(3.0, value))
  }

  function setSelectedText(text: string, position?: { x: number; y: number }) {
    selectedText.value = text
    selectionPosition.value = position || null
  }

  function setSelectionInfo(info: { page: number; rects: NormalizedRect[] } | null) {
    selectionInfo.value = info
  }

  function clearSelection() {
    selectedText.value = ''
    selectionPosition.value = null
    selectionInfo.value = null
  }

  function addHighlightFromSelection() {
    if (!selectionInfo.value || !selectedText.value || !currentDocumentId.value) return

    const docId = currentDocumentId.value
    if (!allHighlights.value[docId]) {
      allHighlights.value[docId] = []
    }

    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    allHighlights.value[docId].push({
      id,
      page: selectionInfo.value.page,
      rects: selectionInfo.value.rects,
      text: selectedText.value,
      color: highlightColor.value
    })
  }

  function getHighlightsByPage(page: number) {
    return highlights.value.filter(h => h.page === page)
  }

  function setHighlightColor(color: string) {
    highlightColor.value = color
  }

  function selectHighlight(highlight: Highlight, position: { x: number; y: number }) {
    selectedHighlight.value = highlight
    isEditingHighlight.value = true
    selectedText.value = highlight.text
    selectionPosition.value = position
  }

  function clearHighlightSelection() {
    selectedHighlight.value = null
    isEditingHighlight.value = false
  }

  function removeHighlight(id: string) {
    if (!currentDocumentId.value) return

    const docId = currentDocumentId.value
    if (allHighlights.value[docId]) {
      allHighlights.value[docId] = allHighlights.value[docId].filter(h => h.id !== id)
    }
    clearHighlightSelection()
  }

  function updateHighlightColor(id: string, color: string) {
    if (!currentDocumentId.value) return

    const docId = currentDocumentId.value
    const highlight = allHighlights.value[docId]?.find(h => h.id === id)
    if (highlight) {
      highlight.color = color
    }
  }

  function getHighlightsAtPoint(page: number, x: number, y: number): Highlight[] {
    return highlights.value.filter(h => {
      if (h.page !== page) return false
      return h.rects.some(rect => {
        return x >= rect.left && x <= rect.left + rect.width &&
               y >= rect.top && y <= rect.top + rect.height
      })
    })
  }

  // 删除文档时清理对应的高亮数据
  function removeDocumentHighlights(documentId: string) {
    if (allHighlights.value[documentId]) {
      delete allHighlights.value[documentId]
      saveHighlightsToStorage()
    }
  }

  function toggleAutoHighlight() {
    autoHighlight.value = !autoHighlight.value
  }

  function toggleAutoTranslate() {
    autoTranslate.value = !autoTranslate.value
  }

  function toggleImageDescription() {
    imageDescription.value = !imageDescription.value
  }

  // 设置文档的段落数据
  function setParagraphs(documentId: string, paragraphsData: PdfParagraph[]) {
    allParagraphs.value[documentId] = paragraphsData
  }

  // 获取指定页面的段落
  function getParagraphsByPage(page: number): PdfParagraph[] {
    return paragraphs.value.filter(p => p.page === page)
  }

  // 打开翻译面板（新版本：支持多窗口）
  function openTranslationPanel(paragraphId: string, position: { x: number; y: number }, originalText: string) {
    // 检查缓存
    const cached = translationCache.value[paragraphId]
    
    // 检查是否已存在该段落的翻译窗口
    const existingPanel = translationPanels.value.find(p => p.paragraphId === paragraphId)
    if (existingPanel) {
      // 已存在，将其移到前面（聚焦）
      const index = translationPanels.value.indexOf(existingPanel)
      translationPanels.value.splice(index, 1)
      translationPanels.value.push(existingPanel)
      return
    }
    
    // 创建新的翻译面板实例
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
    
    // 同时更新旧版状态以保持兼容
    translationPanel.value = {
      isVisible: true,
      paragraphId,
      position,
      translation: cached || '',
      isLoading: !cached,
      originalText
    }
  }

  // 关闭翻译面板（旧版本兼容）
  function closeTranslationPanel() {
    translationPanel.value.isVisible = false
  }
  
  // 关闭指定的翻译面板
  function closeTranslationPanelById(panelId: string) {
    const index = translationPanels.value.findIndex(p => p.id === panelId)
    if (index !== -1) {
      // 从侧边栏列表中移除
      const sidebarIndex = sidebarDockedPanels.value.indexOf(panelId)
      if (sidebarIndex !== -1) {
        sidebarDockedPanels.value.splice(sidebarIndex, 1)
      }
      translationPanels.value.splice(index, 1)
    }
  }

  // 更新翻译面板位置（旧版本兼容）
  function updateTranslationPanelPosition(position: { x: number; y: number }) {
    translationPanel.value.position = position
  }
  
  // 更新指定面板的位置
  function updatePanelPosition(panelId: string, position: { x: number; y: number }) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.position = position
    }
  }
  
  // 更新指定面板的尺寸
  function updatePanelSize(panelId: string, size: { width: number; height: number }) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.size = size
    }
  }
  
  // 设置面板吸附模式
  function setPanelSnapMode(panelId: string, mode: 'none' | 'paragraph' | 'sidebar', targetParagraphId?: string) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.snapMode = mode
      panel.snapTargetParagraphId = targetParagraphId || null
      panel.isSidebarDocked = mode === 'sidebar'
      
      // 管理侧边栏列表
      const sidebarIndex = sidebarDockedPanels.value.indexOf(panelId)
      if (mode === 'sidebar' && sidebarIndex === -1) {
        sidebarDockedPanels.value.push(panelId)
      } else if (mode !== 'sidebar' && sidebarIndex !== -1) {
        sidebarDockedPanels.value.splice(sidebarIndex, 1)
      }
    }
  }

  // 设置翻译结果
  function setTranslation(paragraphId: string, translation: string) {
    translationCache.value[paragraphId] = translation
    
    // 更新旧版状态
    if (translationPanel.value.paragraphId === paragraphId) {
      translationPanel.value.translation = translation
      translationPanel.value.isLoading = false
    }
    
    // 更新所有匹配的面板
    translationPanels.value.forEach(panel => {
      if (panel.paragraphId === paragraphId) {
        panel.translation = translation
        panel.isLoading = false
      }
    })
  }

  // 设置翻译加载状态
  function setTranslationLoading(loading: boolean) {
    translationPanel.value.isLoading = loading
  }
  
  // 设置指定面板的加载状态
  function setPanelLoading(panelId: string, loading: boolean) {
    const panel = translationPanels.value.find(p => p.id === panelId)
    if (panel) {
      panel.isLoading = loading
    }
  }
  
  // 将面板移动到最前面（聚焦）
  function bringPanelToFront(panelId: string) {
    const index = translationPanels.value.findIndex(p => p.id === panelId)
    if (index !== -1 && index !== translationPanels.value.length - 1) {
      const panel = translationPanels.value.splice(index, 1)[0]
      if (panel) {
        translationPanels.value.push(panel)
      }
    }
  }

  return {
    currentPdfUrl,
    currentDocumentId,
    currentPage,
    totalPages,
    scale,
    scalePercent,
    isLoading,
    autoHighlight,
    autoTranslate,
    imageDescription,
    selectedText,
    selectionPosition,
    selectionInfo,
    highlights,
    highlightColor,
    selectedHighlight,
    isEditingHighlight,
    setCurrentPdf,
    setTotalPages,
    goToPage,
    nextPage,
    prevPage,
    zoomIn,
    zoomOut,
    setScale,
    setSelectedText,
    setSelectionInfo,
    clearSelection,
    addHighlightFromSelection,
    getHighlightsByPage,
    setHighlightColor,
    selectHighlight,
    clearHighlightSelection,
    removeHighlight,
    updateHighlightColor,
    getHighlightsAtPoint,
    removeDocumentHighlights,
    toggleAutoHighlight,
    toggleAutoTranslate,
    toggleImageDescription,
    // 段落管理
    paragraphs,
    setParagraphs,
    getParagraphsByPage,
    // 翻译面板
    translationPanel,
    openTranslationPanel,
    closeTranslationPanel,
    updateTranslationPanelPosition,
    setTranslation,
    setTranslationLoading,
    // 多窗口翻译面板
    translationPanels,
    sidebarDockedPanels,
    closeTranslationPanelById,
    updatePanelPosition,
    updatePanelSize,
    setPanelSnapMode,
    setPanelLoading,
    bringPanelToFront,
  }
})
