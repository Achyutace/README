import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

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
  }
})
