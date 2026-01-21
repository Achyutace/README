import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const DEFAULT_SCALE = 1.6

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

export const usePdfStore = defineStore('pdf', () => {
  const currentPdfUrl = ref<string | null>(null)
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
  const highlights = ref<Highlight[]>([])
  const highlightColor = ref('#F6E05E') // bright yellow by default

  const scalePercent = computed(() => Math.round(scale.value * 100))

  function setCurrentPdf(url: string) {
    currentPdfUrl.value = url
    currentPage.value = 1
    scale.value = DEFAULT_SCALE
    isLoading.value = true
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
    if (!selectionInfo.value || !selectedText.value) return

    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    highlights.value.push({
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
    toggleAutoHighlight,
    toggleAutoTranslate,
    toggleImageDescription,
  }
})
