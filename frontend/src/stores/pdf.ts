/*
----------------------------------------------------------------------
                    PDF状态，翻译面板等相关状态管理
----------------------------------------------------------------------
*/ 
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PdfParagraph, TranslationPanelState, TranslationPanelInstance } from '../types'

 // 实际缩放 150%，显示为 100%
const DEFAULT_SCALE = 1.5

// 用于在 localStorage 中存储高亮数据的 key
const HIGHLIGHTS_STORAGE_KEY = 'pdf-highlights' 

// 矩形框（左上角坐标 + 宽高）
type NormalizedRect = {
  left: number
  top: number
  width: number
  height: number
}

// 高亮对象结构
type Highlight = {
  id: string    // 唯一标识符
  page: number    // 所在页码
  rects: NormalizedRect[]    // 该高亮覆盖的多个矩形区域
  text: string    // 高亮的文本内容
  color: string    // 高亮颜色（十六进制字符串）
}

// 存储结构：文档ID -> 高亮列表
type HighlightsStorage = Record<string, Highlight[]>

export type { Highlight, NormalizedRect }

export const usePdfStore = defineStore('pdf', () => {
  // ---------------------- 可观察的状态（state） ----------------------
  const currentPdfUrl = ref<string | null>(null) // 当前打开的 PDF 文件 URL
  const currentDocumentId = ref<string | null>(null) // 当前文档 ID（用于区分不同文档的高亮与段落）
  const currentPage = ref(1) // 当前页码（从 1 开始）
  const totalPages = ref(0) // 文档总页数
  const scale = ref(DEFAULT_SCALE) // 当前缩放比例（内部以 1.5 为基准）
  const isLoading = ref(false) // 文档加载中标志

  // 自动高亮 / 自动翻译 / 图片描述开关
  const autoHighlight = ref(false)
  const autoTranslate = ref(false)
  const imageDescription = ref(false)

  // 文字选择相关信息
  const selectedText = ref<string>('') // 当前被选择的文字内容
  const selectionPosition = ref<{ x: number; y: number } | null>(null) // 选择框在页面上的位置（像素坐标）
  const selectionInfo = ref<{ page: number; rects: NormalizedRect[] } | null>(null) // 详细的选择信息（包含页码与归一化矩形）

  // 所有文档的高亮数据（key: documentId, value: Highlight[]）
  const allHighlights = ref<HighlightsStorage>({})

  // 当前文档的高亮（计算属性，若没有当前文档则返回空数组）
  const highlights = computed(() => {
    if (!currentDocumentId.value) return []
    return allHighlights.value[currentDocumentId.value] || []
  })

  // 默认高亮颜色（亮黄色）
  const highlightColor = ref('#F6E05E') 

  // 当前选中高亮（用于编辑或删除）
  const selectedHighlight = ref<Highlight | null>(null) 

  // 是否处于高亮编辑模式
  const isEditingHighlight = ref(false) 

  // 所有文档的段落数据（用于翻译/定位等功能）
  const allParagraphs = ref<Record<string, PdfParagraph[]>>({})

  // 当前文档的段落（计算属性）
  const paragraphs = computed(() => {
    if (!currentDocumentId.value) return []
    return allParagraphs.value[currentDocumentId.value] || []
  })

  // 兼容旧版的单一翻译面板状态（为向后兼容保留）
  const translationPanel = ref<TranslationPanelState>({
    isVisible: false,
    paragraphId: '',
    position: { x: 0, y: 0 },
    translation: '',
    isLoading: false,
    originalText: ''
  })

  // 翻译面板
  const translationPanels = ref<TranslationPanelInstance[]>([])

  // 侧边栏停靠的翻译面板 ID 列表
  const sidebarDockedPanels = ref<string[]>([])

  // 翻译缓存：paragraphId -> translation
  const translationCache = ref<Record<string, string>>({})

  // UI 显示的缩放百分比
  const scalePercent = computed(() => Math.round((scale.value / DEFAULT_SCALE) * 100))

  // ---------------------- 本地存储（localStorage）读写 ----------------------
  // 从 localStorage 加载高亮数据，避免每次刷新丢失高亮
  function loadHighlightsFromStorage() {
    try {
      const stored = localStorage.getItem(HIGHLIGHTS_STORAGE_KEY)
      if (stored) {
        allHighlights.value = JSON.parse(stored)
      }
    } catch (err) {
      // 读取失败则记录错误，但不影响主流程
      console.error('Failed to load highlights from storage:', err)
    }
  }

  // 将高亮数据保存到 localStorage
  function saveHighlightsToStorage() {
    try {
      localStorage.setItem(HIGHLIGHTS_STORAGE_KEY, JSON.stringify(allHighlights.value))
    } catch (err) {
      // 保存失败通常是因为浏览器存储空间或隐私策略
      console.error('Failed to save highlights to storage:', err)
    }
  }

  // 初始化时从 localStorage 加载已有高亮
  loadHighlightsFromStorage()

  // 监听高亮对象变化并自动保存（深度观察）
  watch(allHighlights, () => {
    saveHighlightsToStorage()
  }, { deep: true })

  // ---------------------- 文档与页面控制 ----------------------
  // 设置当前打开的 PDF（可包含 documentId 用于区分不同文档）
  function setCurrentPdf(url: string, documentId?: string) {
    // 切换文档时清除已有选择和高亮选中状态，避免悬浮 UI 残留
    clearSelection()
    clearHighlightSelection()

    currentPdfUrl.value = url
    currentDocumentId.value = documentId || null
    currentPage.value = 1
    scale.value = DEFAULT_SCALE
    isLoading.value = true

    // 确保当前文档在高亮存储中存在对应数组（避免未定义访问）
    if (documentId && !allHighlights.value[documentId]) {
      allHighlights.value[documentId] = []
    }
  }

  // 设置文档总页数并结束加载状态
  function setTotalPages(pages: number) {
    totalPages.value = pages
    isLoading.value = false
  }

  // 跳转到指定页（有边界检查）
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

  // 缩放控制：逐步放大
  function zoomIn() {
    if (scale.value < 4.5) {
      scale.value = Math.min(4.5, scale.value + 0.1)
    }
  }

  // 缩放控制：逐步缩小
  function zoomOut() {
    if (scale.value > 0.5) {
      scale.value = Math.max(0.5, scale.value - 0.1)
    }
  }

  // 缩放最大最小限制在 0.5（约 33%） 到 4.5（约 300%） 之间
  function setScale(value: number) {
    scale.value = Math.max(0.5, Math.min(4.5, value))
  }

  // ---------------------- 文本选择与高亮功能 ----------------------
  // 设置被选择的文字和其屏幕位置（用于显示翻译/笔记悬浮框）
  function setSelectedText(text: string, position?: { x: number; y: number }) {
    selectedText.value = text
    selectionPosition.value = position || null
  }

  // 存储选择的详细信息（页码 + 选中字矩形集合）
  function setSelectionInfo(info: { page: number; rects: NormalizedRect[] } | null) {
    selectionInfo.value = info
  }

  // 清空当前选择相关状态
  function clearSelection() {
    selectedText.value = ''
    selectionPosition.value = null
    selectionInfo.value = null
  }

  // 从当前选择创建一个高亮并保存到当前文档
  function addHighlightFromSelection() {
    // 需要有选择信息、选中文本且存在当前文档 ID
    if (!selectionInfo.value || !selectedText.value || !currentDocumentId.value) return

    const docId = currentDocumentId.value
    if (!allHighlights.value[docId]) {
      allHighlights.value[docId] = []
    }

    // 生成一个唯一 id（时间戳 + 随机片段）
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    allHighlights.value[docId].push({
      id,
      page: selectionInfo.value.page,
      rects: selectionInfo.value.rects,
      text: selectedText.value,
      color: highlightColor.value
    })
  }

  // 获取指定页面的高亮列表
  function getHighlightsByPage(page: number) {
    return highlights.value.filter(h => h.page === page)
  }

  // 设置默认高亮颜色
  function setHighlightColor(color: string) {
    highlightColor.value = color
  }

  // 选中某个高亮（用于展示编辑 / 删除菜单）
  function selectHighlight(highlight: Highlight, position: { x: number; y: number }) {
    selectedHighlight.value = highlight
    isEditingHighlight.value = true
    selectedText.value = highlight.text
    selectionPosition.value = position
  }

  // 清理高亮的选中状态
  function clearHighlightSelection() {
    selectedHighlight.value = null
    isEditingHighlight.value = false
  }

  // 删除当前文档下的某条高亮
  function removeHighlight(id: string) {
    if (!currentDocumentId.value) return

    const docId = currentDocumentId.value
    if (allHighlights.value[docId]) {
      allHighlights.value[docId] = allHighlights.value[docId].filter(h => h.id !== id)
    }
    clearHighlightSelection()
  }

  // 更新某条高亮的颜色
  function updateHighlightColor(id: string, color: string) {
    if (!currentDocumentId.value) return

    const docId = currentDocumentId.value
    const highlight = allHighlights.value[docId]?.find(h => h.id === id)
    if (highlight) {
      highlight.color = color
    }
  }

  // 判断某个点（x,y）是否落在页面的高亮区域内，并返回相关高亮
  function getHighlightsAtPoint(page: number, x: number, y: number): Highlight[] {
    return highlights.value.filter(h => {
      if (h.page !== page) return false
      return h.rects.some(rect => {
        return x >= rect.left && x <= rect.left + rect.width &&
               y >= rect.top && y <= rect.top + rect.height
      })
    })
  }

  // 删除整个文档对应的高亮数据（例如删除文档或清理数据时使用）
  function removeDocumentHighlights(documentId: string) {
    if (allHighlights.value[documentId]) {
      delete allHighlights.value[documentId]
      saveHighlightsToStorage() // 删除后立即持久化
    }
  }

  // ---------------------- 功能开关 ----------------------
  function toggleAutoHighlight() {
    autoHighlight.value = !autoHighlight.value
  }

  function toggleAutoTranslate() {
    autoTranslate.value = !autoTranslate.value
  }

  function toggleImageDescription() {
    imageDescription.value = !imageDescription.value
  }

  // ---------------------- 段落管理 ----------------------
  // 为某个文档设置段落数据（通常由解析 PDF 得到）
  function setParagraphs(documentId: string, paragraphsData: PdfParagraph[]) {
    allParagraphs.value[documentId] = paragraphsData
  }

  // 获取指定页面对应的段落列表（用于显示翻译、跳转等）
  function getParagraphsByPage(page: number): PdfParagraph[] {
    return paragraphs.value.filter(p => p.page === page)
  }

  // ---------------------- 翻译面板（单窗口兼容 + 多窗口） ----------------------
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

  // ---------------------- 笔记预览卡片（小悬浮卡片） ----------------------
  const notePreviewCard = ref<{
    isVisible: boolean
    note: { id: number | string; title: string; content: string } | null
    position: { x: number; y: number }
  }>({
    isVisible: false,
    note: null,
    position: { x: 0, y: 0 }
  })

  // 打开笔记预览卡片并设置其位置
  function openNotePreviewCard(note: { id: number | string; title: string; content: string }, position: { x: number; y: number }) {
    notePreviewCard.value = {
      isVisible: true,
      note,
      position
    }
  }

  // 关闭并重置笔记预览卡片
  function closeNotePreviewCard() {
    notePreviewCard.value = {
      isVisible: false,
      note: null,
      position: { x: 0, y: 0 }
    }
  }

  // 更新笔记预览卡片位置
  function updateNotePreviewPosition(position: { x: number; y: number }) {
    notePreviewCard.value.position = position
  }

  // ---------------------- 智能引用卡片（如论文引用详情） ----------------------
  const smartRefCard = ref<{
    isVisible: boolean
    isLoading: boolean
    paper: any | null
    position: { x: number; y: number }
    error?: string | null
  }>({
    isVisible: false,
    isLoading: false,
    paper: null,
    position: { x: 0, y: 0 },
    error: null
  })

  function openSmartRefCard(paperData: any, position: { x: number; y: number }) {
    smartRefCard.value = {
      isVisible: true,
      isLoading: false,
      paper: paperData,
      position,
      error: null
    }
  }

  function closeSmartRefCard() {
    smartRefCard.value.isVisible = false
  }

  function updateSmartRefPosition(position: { x: number; y: number }) {
    smartRefCard.value.position = position
  }

  // ---------------------- 导出 store 接口 ----------------------
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
    // 笔记预览卡片
    notePreviewCard,
    openNotePreviewCard,
    closeNotePreviewCard,
    updateNotePreviewPosition,
    // 智能引用卡片
    smartRefCard,
    openSmartRefCard,
    closeSmartRefCard,
    updateSmartRefPosition,
  }
})
