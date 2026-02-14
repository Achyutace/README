/*
----------------------------------------------------------------------
                    PDF状态，翻译面板等相关状态管理
----------------------------------------------------------------------
*/ 
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PdfParagraph } from '../types'
import type { PageSize } from '../types/pdf'
import type { InternalLinkData } from '../api'

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

  // 页面尺寸数据（用于坐标转换等）
  const pageSizesConstant = ref<PageSize | null>(null)
  const pageSizesArray = ref<PageSize[] | null>(null)

  // 当前文档的段落（计算属性）
  const paragraphs = computed(() => {
    if (!currentDocumentId.value) return []
    return allParagraphs.value[currentDocumentId.value] || []
  })



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
    } else {
      console.warn(`Invalid page number: ${page}, valid range: 1-${totalPages.value}`)
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

  function setScalePercent(percent: number) {
    const newScale = (percent / 100) * DEFAULT_SCALE
    setScale(newScale)
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
    if (!selectionInfo.value || !selectedText.value || !currentDocumentId.value) {
      if (!selectionInfo.value) console.warn('Cannot add highlight: no selection info')
      if (!selectedText.value) console.warn('Cannot add highlight: no selected text')
      if (!currentDocumentId.value) console.warn('Cannot add highlight: no document ID')
      return
    }

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
    if (!currentDocumentId.value) {
      console.warn('Cannot remove highlight: no current document')
      return
    }

    const docId = currentDocumentId.value
    if (allHighlights.value[docId]) {
      const beforeLength = allHighlights.value[docId].length
      allHighlights.value[docId] = allHighlights.value[docId].filter(h => h.id !== id)
      if (allHighlights.value[docId].length === beforeLength) {
        console.warn(`Highlight ${id} not found in document ${docId}`)
      }
    } else {
      console.warn(`No highlights found for document ${docId}`)
    }
    clearHighlightSelection()
  }

  // 更新某条高亮的颜色
  function updateHighlightColor(id: string, color: string) {
    if (!currentDocumentId.value) {
      console.warn('Cannot update highlight color: no current document')
      return
    }

    const docId = currentDocumentId.value
    const highlight = allHighlights.value[docId]?.find(h => h.id === id)
    if (highlight) {
      highlight.color = color
    } else {
      console.warn(`Highlight ${id} not found in document ${docId} for color update`)
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

  // 设置页面尺寸数据
  function setPageSizes(constant: PageSize | null, array: PageSize[] | null) {
    pageSizesConstant.value = constant
    pageSizesArray.value = array
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

  // ---------------------- 内部链接弹窗 ----------------------
  /** PDF 内部链接目标坐标 */
  type DestinationCoords = {
    page: number
    x: number | null
    y: number | null
    zoom: number | null
    type: string
  }

  const internalLinkPopup = ref<{
    isVisible: boolean
    destCoords: DestinationCoords | null
    position: { x: number; y: number }
    linkData: InternalLinkData | null
    paragraphContent: string | null
    isLoading: boolean
    error: string | null
  }>({
    isVisible: false,
    destCoords: null,
    position: { x: 0, y: 0 },
    linkData: null,
    paragraphContent: null,
    isLoading: false,
    error: null
  })

  function openInternalLinkPopup(destCoords: DestinationCoords, position: { x: number; y: number }) {
    internalLinkPopup.value = {
      isVisible: true,
      destCoords,
      position,
      linkData: null,
      paragraphContent: null,
      isLoading: false,
      error: null
    }
  }

  function closeInternalLinkPopup() {
    internalLinkPopup.value.isVisible = false
  }

  function updateInternalLinkPopupPosition(position: { x: number; y: number }) {
    internalLinkPopup.value.position = position
  }

  function setInternalLinkData(data: InternalLinkData | null, paragraphContent?: string, error?: string) {
    internalLinkPopup.value.linkData = data
    internalLinkPopup.value.paragraphContent = paragraphContent || null
    internalLinkPopup.value.error = error || null
  }

  function setInternalLinkLoading(loading: boolean) {
    internalLinkPopup.value.isLoading = loading
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
    setScalePercent,
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
    // 页面尺寸
    pageSizesConstant,
    pageSizesArray,
    setPageSizes,
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
    // 内部链接弹窗
    internalLinkPopup,
    openInternalLinkPopup,
    closeInternalLinkPopup,
    updateInternalLinkPopupPosition,
    setInternalLinkData,
    setInternalLinkLoading,
  }
})
