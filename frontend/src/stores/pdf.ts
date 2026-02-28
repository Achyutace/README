import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfParagraph, Highlight, NormalizedRect, HighlightsStorage } from '../types'
import type { PageSize } from '../types/pdf'
import { highlightApi } from '../api'

// 导入解耦后的子模块逻辑
import { usePdfUiState } from './pdf-ui'
import { usePdfTranslationState } from './pdf-translation'

// 实际缩放 150%，显示为 100%
const DEFAULT_SCALE = 1.5

export type { Highlight, NormalizedRect }

export const usePdfStore = defineStore('pdf', () => {
  // ---------------------- 实例化解耦后的子模块 ----------------------
  const ui = usePdfUiState()
  const translation = usePdfTranslationState()

  // ---------------------- 可观察的状态（state） ----------------------
  const currentPdfUrl = ref<string | null>(null) // 当前打开的 PDF 文件 URL
  const activeReaderId = ref<string | null>(null) // 当前文档 ID
  const currentPage = ref(1) // 当前页码（从 1 开始）
  const totalPages = ref(0) // 文档总页数
  const scale = ref(DEFAULT_SCALE) // 当前缩放比例
  const isLoading = ref(false) // 文档加载中标志

  // 自动相关开关
  const autoHighlight = ref(false)
  const autoTranslate = ref(false)
  const imageDescription = ref(false)

  // 文字选择相关信息
  const selectedText = ref<string>('')
  const selectionPosition = ref<{ x: number; y: number } | null>(null)
  const selectionInfo = ref<{ page: number; rects: NormalizedRect[] } | null>(null)

  // 存储数据
  const allHighlights = ref<HighlightsStorage>({})
  const allParagraphs = ref<Record<string, PdfParagraph[]>>({})
  const pageSizesConstant = ref<PageSize | null>(null)
  const pageSizesArray = ref<PageSize[] | null>(null)

  const highlightColor = ref('#F6E05E')
  const selectedHighlight = ref<Highlight | null>(null)
  const isEditingHighlight = ref(false)

  // ---------------------- 计算属性 ----------------------
  const highlights = computed(() => {
    if (!activeReaderId.value) return []
    return allHighlights.value[activeReaderId.value] || []
  })

  const paragraphs = computed(() => {
    if (!activeReaderId.value) return []
    return allParagraphs.value[activeReaderId.value] || []
  })

  const scalePercent = computed(() => Math.round((scale.value / DEFAULT_SCALE) * 100))

  // ---------------------- 文档与页面控制 ----------------------
  function setCurrentPdf(url: string, documentId?: string) {
    clearSelection()
    clearHighlightSelection()
    currentPdfUrl.value = url
    activeReaderId.value = documentId || null
    currentPage.value = 1
    scale.value = DEFAULT_SCALE
    isLoading.value = true

    // 重置子模块状态
    translation.pageTranslationStatus.value = {}
    translation.fullTranslationStatus.value = 'idle'

    if (documentId) {
      if (!allHighlights.value[documentId]) {
        allHighlights.value[documentId] = []
      }
      fetchHighlightsForPdf(documentId)
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

  function nextPage() { goToPage(currentPage.value + 1) }
  function prevPage() { goToPage(currentPage.value - 1) }

  function zoomIn() { if (scale.value < 4.5) scale.value = Math.min(4.5, scale.value + 0.1) }
  function zoomOut() { if (scale.value > 0.5) scale.value = Math.max(0.5, scale.value - 0.1) }

  function setScale(value: number) { scale.value = Math.max(0.5, Math.min(4.5, value)) }
  function setScalePercent(percent: number) { setScale((percent / 100) * DEFAULT_SCALE) }

  // ---------------------- 文本选择与高亮功能 ----------------------
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

  async function addHighlightFromSelection() {
    if (!selectionInfo.value || !selectedText.value || !activeReaderId.value) return
    const docId = activeReaderId.value
    const page = selectionInfo.value.page
    const pageData = pageSizesArray.value?.[page - 1] || pageSizesConstant.value

    try {
      const res = await highlightApi.createHighlight({
        pdfId: docId,
        page,
        rects: selectionInfo.value.rects,
        pageWidth: pageData?.width || 800,
        pageHeight: pageData?.height || 1200,
        text: selectedText.value,
        color: highlightColor.value
      })
      if (res.success) {
        await fetchHighlightsForPdf(docId)
        import('../utils/broadcast').then(({ broadcastSync }) => broadcastSync('RELOAD_HIGHLIGHTS', docId))
      }
    } catch (error) {
      console.error('Failed to create highlight remotely', error)
    }
    clearSelection()
  }

  function getHighlightsByPage(page: number) {
    return highlights.value.filter(h => h.page === page)
  }

  function setHighlightColor(color: string) { highlightColor.value = color }

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

  async function removeHighlight(id: string) {
    if (!activeReaderId.value) return
    const docId = activeReaderId.value
    try {
      await highlightApi.deleteHighlight(id)
      if (allHighlights.value[docId]) {
        allHighlights.value[docId] = allHighlights.value[docId].filter(h => String(h.id) !== String(id))
      }
      clearHighlightSelection()
      import('../utils/broadcast').then(({ broadcastSync }) => broadcastSync('RELOAD_HIGHLIGHTS', docId))
    } catch (e) {
      console.error("Failed to delete remote highlight:", e)
    }
  }

  async function updateHighlightColor(id: string, color: string) {
    if (!activeReaderId.value) return
    const docId = activeReaderId.value
    try {
      await highlightApi.updateHighlight(id, color)
      const highlight = allHighlights.value[docId]?.find(h => String(h.id) === String(id))
      if (highlight) {
        highlight.color = color
        import('../utils/broadcast').then(({ broadcastSync }) => broadcastSync('RELOAD_HIGHLIGHTS', docId))
      }
    } catch (e) {
      console.error("Failed to update remote highlight:", e)
    }
  }

  function getHighlightsAtPoint(page: number, x: number, y: number): Highlight[] {
    return highlights.value.filter(h => {
      if (h.page !== page) return false
      return h.rects.some(rect => x >= rect.left && x <= rect.left + rect.width && y >= rect.top && y <= rect.top + rect.height)
    })
  }

  function removeDocumentHighlights(documentId: string) {
    if (allHighlights.value[documentId]) {
      delete allHighlights.value[documentId]
      import('../utils/broadcast').then(({ broadcastSync }) => broadcastSync('RELOAD_HIGHLIGHTS', documentId))
    }
  }

  // ---------------------- 其他逻辑封装 ----------------------
  function toggleAutoHighlight() { autoHighlight.value = !autoHighlight.value }
  function toggleAutoTranslate() { autoTranslate.value = !autoTranslate.value }
  function toggleImageDescription() { imageDescription.value = !imageDescription.value }

  function setParagraphs(documentId: string, paragraphsData: PdfParagraph[]) {
    allParagraphs.value[documentId] = paragraphsData
  }

  function appendParagraphs(documentId: string, newParagraphs: PdfParagraph[]) {
    if (!newParagraphs.length) return
    const existing = allParagraphs.value[documentId] ?? []

    // Deduplicate by ID AND by spatial location (page + bbox) to handle backend restarts
    const existingIds = new Set(existing.map(p => p.id))
    const getSpatialKey = (p: PdfParagraph) => `${p.page}-${Math.round(p.bbox.x0)}-${Math.round(p.bbox.y0)}`
    const existingLocations = new Set(existing.map(getSpatialKey))

    const toAdd = newParagraphs.filter(p => {
      const loc = getSpatialKey(p)
      if (existingIds.has(p.id) || existingLocations.has(loc)) {
        // We already have this paragraph, update its translation text if the new one has it and we don't
        const existingPara = existing.find(ep => ep.id === p.id || getSpatialKey(ep) === loc)
        if (existingPara && p.translation && !existingPara.translation) {
          existingPara.translation = p.translation
        }
        return false
      }
      return true
    })

    if (!toAdd.length) {
      // Force reactivity update in case we only updated translations
      allParagraphs.value[documentId] = [...existing]
      return
    }

    const merged = [...existing, ...toAdd]
    merged.sort((a, b) => a.page - b.page || (a.bbox?.y0 ?? 0) - (b.bbox?.y0 ?? 0))
    allParagraphs.value[documentId] = merged
  }

  function getParagraphsByPage(page: number): PdfParagraph[] {
    return paragraphs.value.filter(p => p.page === page)
  }

  function setPageSizes(constant: PageSize | null, array: PageSize[] | null) {
    pageSizesConstant.value = constant
    pageSizesArray.value = array
  }

  async function fetchHighlightsForPdf(pdfId: string) {
    try {
      const { success, highlights: hList } = await highlightApi.getHighlights(pdfId)
      if (success && Array.isArray(hList)) {
        allHighlights.value[pdfId] = hList.map(item => ({
          id: String(item.id),
          page: item.page_number,
          rects: Array.isArray(item.rects)
            ? item.rects.map((r: any) => ({ left: r.x, top: r.y, width: r.width, height: r.height }))
            : [],
          text: item.selected_text || '',
          color: item.color || '#FFFF00'
        }))
      }
    } catch (e) {
      console.error('Failed to reload highlights', e)
    }
  }

  // ---------------------- 跨标签监听 ----------------------
  import('../utils/broadcast').then(({ syncChannel }) => {
    syncChannel.addEventListener('message', (event) => {
      const { type, payload } = event.data
      if (type === 'RELOAD_HIGHLIGHTS' && payload === activeReaderId.value) {
        fetchHighlightsForPdf(payload)
      }
    })
  }).catch(e => console.error("Broadcast failed", e))

  // ---------------------- 桥接翻译与 UI 逻辑 ----------------------
  const startPagePreTranslation = (pageNumber: number, skipIfProcessing = true) =>
    translation.startPagePreTranslation(pageNumber, activeReaderId.value!, allParagraphs.value, skipIfProcessing)

  const startFullPreTranslation = () =>
    translation.startFullPreTranslation(activeReaderId.value!, totalPages.value, allParagraphs.value, translation.startPagePreTranslation)

  // ---------------------- 返回 Store 接口 ----------------------
  return {
    ...ui, // 展开所有 UI 相关的 state 和 actions
    currentPdfUrl,
    activeReaderId,
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
    paragraphs,
    setParagraphs,
    appendParagraphs,
    getParagraphsByPage,
    pageSizesConstant,
    pageSizesArray,
    setPageSizes,
    // 桥接翻译状态
    pageTranslationStatus: translation.pageTranslationStatus,
    fullTranslationStatus: translation.fullTranslationStatus,
    startPagePreTranslation,
    startFullPreTranslation,
  }
})
