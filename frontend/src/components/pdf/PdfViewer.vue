<script setup lang="ts">
/*
----------------------------------------------------------------------
                            Pdf 查看器组件
----------------------------------------------------------------------
*/ 

// ------------------------- 导入依赖与组件 -------------------------
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue' 
import { useDebounceFn } from '@vueuse/core' 
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
  type RenderTask,
} from 'pdfjs-dist' 
import 'pdfjs-dist/web/pdf_viewer.css' 

import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.js?url' 
import { usePdfStore } from '../../stores/pdf' 
import { useTranslationStore } from '../../stores/translation'
import { useLibraryStore } from '../../stores/library' 
import { notesApi, type Note } from '../../api' 
import { clamp } from '@vueuse/core'

// 导入拆分出的模块
import type { PageRef, PageSize } from '../../types/pdf'
import {
  getPageSize,
  getScaledPageSize,
  getPageTop,
  getPageAtY,
  findPageElement,
  getHighlightColor,
  getBoundingBoxStyle,
  getParagraphMarkerStyle,
  CLICK_TIME_THRESHOLD,
  DRAG_DISTANCE_THRESHOLD
} from '../../utils/PdfHelper'
import { applyInterimScaleToPage, fetchInternalLinkData } from '../../utils/PdfRender'
import { useZoomAnchor } from '../../composables/useZoomAnchor'
import { usePageRender } from '../../composables/usePageRender'
import { usePdfSelection } from '../../composables/usePdfSelection'
import { useNotesLookup } from '../../composables/useNotesLookup'

import TextSelectionTooltip from './TextSelectionTooltip.vue' 
import TranslationPanel from './TranslationPanel.vue' 
import NotePreviewCard from './NotePreviewCard.vue'
import InternalLinkPopup from './InternalLinkPopup.vue' 

GlobalWorkerOptions.workerSrc = pdfWorker

// ------------------------- 初始化 store 实例 -------------------------
const pdfStore = usePdfStore() 
const libraryStore = useLibraryStore() 
const translationStore = useTranslationStore()

// ------------------------- 初始化 PDF 状态与引用 -------------------------
const containerRef = ref<HTMLElement | null>(null) 
const pdfDoc = shallowRef<PDFDocumentProxy | null>(null) 
const pageNumbers = ref<number[]>([]) 
const pageRefs = new Map<number, PageRef>() 
const renderTasks = new Map<number, RenderTask>() 
const pagesNeedingRefresh = new Set<number>()
const lastRenderedScale = new Map<number, number>() 

const pageSizesConstant = ref<PageSize | null>(null)
const pageSizesArray = ref<PageSize[] | null>(null)
const pageHeightAccumulator = ref<number[]>([])

const renderedPages = ref<Set<number>>(new Set())
const isZooming = ref(false)
const isPointerOverPdf = ref(false)

const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

const highlightsAtCurrentPoint = ref<ReturnType<typeof pdfStore.getHighlightsAtPoint>>([])
const currentHighlightIndex = ref(0)

const mouseDownInfo = ref<{ x: number; y: number; time: number } | null>(null)
const linksDisabled = ref(false)

const preloadProgress = ref(0)
const isPreloading = ref(false)
let preloadAbortController: AbortController | null = null

let resizeObserver: ResizeObserver | null = null
let resizeTimeout: ReturnType<typeof setTimeout> | null = null
const isResizing = ref(false)

const notesCache = ref<Note[]>([])

// Zoom 节流相关
let zoomRafId: number | null = null
let pendingZoomDelta = 0
let lastZoomEvent: WheelEvent | null = null

// ------------------------- 初始化 composables -------------------------
const scaleRef = computed(() => pdfStore.scale)
const {
  pendingAnchor,
  captureCenterAnchor,
  restoreAnchor,
  setPendingAnchor,
  clearPendingAnchor
} = useZoomAnchor(
  containerRef,
  pageNumbers,
  pageRefs,
  pageSizesConstant,
  pageHeightAccumulator,
  scaleRef
)

const {
  updateVisiblePages,
  renderPage,
  scrollToPage
} = usePageRender(
  containerRef,
  pdfDoc,
  pageNumbers,
  pageRefs,
  renderTasks,
  renderedPages,
  pagesNeedingRefresh,
  lastRenderedScale,
  pageSizesConstant,
  pageSizesArray,
  pageHeightAccumulator,
  scaleRef,
  isZooming
)

const {
  handleTextSelection,
} = usePdfSelection({
  onTextSelected: (text, position, page, rects) => {
    pdfStore.setSelectedText(text, position)
    pdfStore.setSelectionInfo({ page, rects })
    tooltipPosition.value = position
    showTooltip.value = true
  },
  onHighlightSelected: (highlight, position) => {
    pdfStore.selectHighlight(highlight, position)
  },
  onClickOutside: handleClickOutside,
  getHighlightsAtPoint: pdfStore.getHighlightsAtPoint.bind(pdfStore)
})

const {
  loadNotesCache,
  handleCtrlClick
} = useNotesLookup({
  getNotes: notesApi.getNotes.bind(notesApi),
  getCurrentDocumentId: () => libraryStore.currentDocument?.id,
  onNoteFound: (note, position) => {
    pdfStore.closeNotePreviewCard()
    pdfStore.openNotePreviewCard(
      { id: note.id, title: note.title, content: note.content },
      position
    )
  }
})

// ------------------------- 事件监听与响应式处理 -------------------------
const settleZooming = useDebounceFn(() => {
  isZooming.value = false
  updateVisiblePages()
  startBackgroundPreload()
}, 180)

// ------------------------- 辅助函数 -------------------------
function isPageRendered(pageNumber: number): boolean {
  return renderedPages.value.has(pageNumber)
}

// ------------------------- 引用处理与资源管理 -------------------------
function handlePageContainerRef(
  pageNumber: number,
  el: Element | { $el: Element } | null
) {
  const htmlEl = el instanceof HTMLElement ? el : null
  setPageRef(pageNumber, htmlEl)
}

function setPageRef(pageNumber: number, el: HTMLElement | null) {
  if (!el) {
    pageRefs.delete(pageNumber)
    return
  }

  const canvas = el.querySelector('canvas')
  const textLayer = el.querySelector('.textLayer')
  const linkLayer = el.querySelector('.linkLayer')
  const highlightLayer = el.querySelector('.highlightLayer')

  if (
    canvas instanceof HTMLCanvasElement &&
    textLayer instanceof HTMLDivElement &&
    linkLayer instanceof HTMLDivElement &&
    highlightLayer instanceof HTMLDivElement
  ) {
    pageRefs.set(pageNumber, {
      container: el,
      canvas,
      textLayer,
      linkLayer,
      highlightLayer
    })
  } else {
    console.warn(
      `Failed to set page ref for page ${pageNumber}: missing required elements. ` +
      `canvas: ${!!canvas}, textLayer: ${!!textLayer}, linkLayer: ${!!linkLayer}, highlightLayer: ${!!highlightLayer}`
    )
  }
}

// ------------------------- 渲染核心与监听调度 -------------------------
const handleScroll = useDebounceFn(() => {
  if (!containerRef.value) return

  updateVisiblePages()

  const scrollTop = containerRef.value.scrollTop
  const p = getPageAtY(
    scrollTop,
    pageNumbers.value.length,
    pdfStore.scale,
    pageSizesConstant.value,
    pageHeightAccumulator.value
  )

  let nearestPage = p
  const minDistance = Math.abs(getPageTop(p, pdfStore.scale, pageSizesConstant.value, pageHeightAccumulator.value) - scrollTop)

  if (p < pdfStore.totalPages) {
    const nextP = p + 1
    const distNext = Math.abs(getPageTop(nextP, pdfStore.scale, pageSizesConstant.value, pageHeightAccumulator.value) - scrollTop)
    if (distNext < minDistance) {
      nearestPage = nextP
    }
  }

  // 仅更新页码显示，不触发滚动对齐
  if (nearestPage !== pdfStore.currentPage && nearestPage <= pdfStore.totalPages) {
    lastUserTriggeredPage = nearestPage
    pdfStore.goToPage(nearestPage)
  }
}, 50)

// ------------------------- PDF 文档加载与预加载策略 -------------------------
async function loadPdf(url: string) {
  cleanup()
  pdfStore.isLoading = true

  const loadingTask = getDocument({
    url,
    cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
    cMapPacked: true
  })

  const pdf = await loadingTask.promise
  pdfDoc.value = pdf
  pdfStore.setTotalPages(pdf.numPages)
  
  if (libraryStore.currentDocumentId) {
    libraryStore.updateDocumentPageCount(libraryStore.currentDocumentId, pdf.numPages)
  }

  await preloadPageSizes(pdf)
  pageNumbers.value = Array.from({ length: pdf.numPages }, (_, index) => index + 1)

  pdfStore.isLoading = false
  await nextTick()

  updateVisiblePages()
  setTimeout(() => startBackgroundPreload(), 500)
}

async function preloadPageSizes(pdf: PDFDocumentProxy) {
  const tempSizes: PageSize[] = []
  const tempAccumulator: number[] = [0]
  let currentAccHeight = 0
  let allSameSize = true
  let firstSize: PageSize | null = null

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i)
    const viewport = page.getViewport({ scale: 1 })
    const size: PageSize = { width: viewport.width, height: viewport.height }

    if (i === 1) {
      firstSize = size
    } else if (firstSize) {
      if (Math.abs(size.width - firstSize.width) > 1 || Math.abs(size.height - firstSize.height) > 1) {
        allSameSize = false
      }
    }

    tempSizes.push(size)
    currentAccHeight += size.height
    if (i < pdf.numPages) {
      tempAccumulator.push(currentAccHeight)
    }
  }

  if (allSameSize && firstSize) {
    console.log(`All pages have the same size: ${firstSize.width}x${firstSize.height}. Using constant size optimization.`)
    pageSizesConstant.value = firstSize
    pageSizesArray.value = null
    pageHeightAccumulator.value = []
  } else {
    pageSizesConstant.value = null
    pageSizesArray.value = tempSizes
    pageHeightAccumulator.value = tempAccumulator
  }
}

async function startBackgroundPreload() {
  const pdf = pdfDoc.value
  if (!pdf) return

  if (preloadAbortController) {
    preloadAbortController.abort()
  }
  preloadAbortController = new AbortController()
  const signal = preloadAbortController.signal

  isPreloading.value = true
  preloadProgress.value = 0

  const totalPages = pdf.numPages
  let loadedCount = 0

  for (let pageNumber = 1; pageNumber <= totalPages; pageNumber++) {
    if (signal.aborted) break

    if (renderedPages.value.has(pageNumber)) {
      loadedCount++
      preloadProgress.value = Math.round((loadedCount / totalPages) * 100)
      continue
    }

    const refs = pageRefs.get(pageNumber)
    if (refs && !renderTasks.has(pageNumber)) {
      await new Promise<void>((resolve) => {
        if ('requestIdleCallback' in window) {
          requestIdleCallback(() => {
            if (!signal.aborted) renderPage(pageNumber)
            resolve()
          }, { timeout: 100 })
        } else {
          setTimeout(() => {
            if (!signal.aborted) renderPage(pageNumber)
            resolve()
          }, 10)
        }
      })
      await new Promise(resolve => setTimeout(resolve, 50))
    }

    loadedCount++
    preloadProgress.value = Math.round((loadedCount / totalPages) * 100)
  }

  isPreloading.value = false
  preloadProgress.value = 100
}

function cleanup() {
  if (preloadAbortController) {
    preloadAbortController.abort()
    preloadAbortController = null
  }
  isPreloading.value = false
  preloadProgress.value = 0

  renderTasks.forEach((task) => task.cancel())
  renderTasks.clear()
  pageRefs.clear()
  pageNumbers.value = []
  pageSizesConstant.value = null
  pageSizesArray.value = null
  pageHeightAccumulator.value = []
  renderedPages.value = new Set()
  pagesNeedingRefresh.clear()
  lastRenderedScale.clear()
  isZooming.value = false
  pdfDoc.value = null

  // 清理 zoom RAF
  if (zoomRafId) {
    cancelAnimationFrame(zoomRafId)
    zoomRafId = null
  }
  pendingZoomDelta = 0
  lastZoomEvent = null
}

// ------------------------- 交互处理 -------------------------
function applyInterimScale() {
  pageRefs.forEach((refs, pageNumber) => {
    const size = getPageSize(pageNumber, pageSizesConstant.value, pageSizesArray.value)
    if (!size) return

    applyInterimScaleToPage(
      refs,
      pageNumber,
      pdfStore.scale,
      lastRenderedScale.get(pageNumber),
      size
    )
  })
}

function handleMouseEnterContainer() {
  isPointerOverPdf.value = true
}

function handleMouseLeaveContainer() {
  isPointerOverPdf.value = false
  linksDisabled.value = false
}

function handleWheel(event: WheelEvent) {
  if (!isPointerOverPdf.value) return

  const container = containerRef.value
  if (!container) return

  if (event.ctrlKey) {
    event.preventDefault()
    event.stopPropagation()

    // 累积 delta，使用 RAF 节流
    pendingZoomDelta += event.deltaY
    lastZoomEvent = event

    if (zoomRafId) return // 已有待执行的帧，直接返回

    zoomRafId = requestAnimationFrame(() => {
      zoomRafId = null

      const isHorizontalOverflow = container.scrollWidth > container.clientWidth + 1

      if (isHorizontalOverflow && lastZoomEvent) {
        setPendingAnchor(captureCenterAnchor({ x: lastZoomEvent.clientX, y: lastZoomEvent.clientY }))
      } else {
        setPendingAnchor(captureCenterAnchor())
      }

      const step = clamp(Math.abs(pendingZoomDelta) / 100, 0.05, 0.25)
      const nextScale = pendingZoomDelta < 0 ? pdfStore.scale + step : pdfStore.scale - step
      pdfStore.setScale(nextScale)

      pendingZoomDelta = 0
      lastZoomEvent = null
    })
    return
  }

  const deltaX = event.deltaX
  if (Math.abs(deltaX) > Math.abs(event.deltaY) * 0.5) {
    const scrollLeft = container.scrollLeft
    const maxScrollLeft = container.scrollWidth - container.clientWidth
    const canScrollRight = scrollLeft < maxScrollLeft - 1
    const canScrollLeft = scrollLeft > 1

    if ((deltaX > 0 && canScrollRight) || (deltaX < 0 && canScrollLeft)) {
      container.scrollLeft = Math.round(container.scrollLeft + deltaX)
      event.preventDefault()
    }
  }
}

function handleMouseMove(event: MouseEvent) {
  const down = mouseDownInfo.value
  if (!down || linksDisabled.value) return

  const elapsed = Date.now() - down.time
  const dx = event.clientX - down.x
  const dy = event.clientY - down.y
  const dist = Math.hypot(dx, dy)

  if (elapsed >= CLICK_TIME_THRESHOLD || dist >= DRAG_DISTANCE_THRESHOLD) {
    linksDisabled.value = true
  }
}

function handleMouseDown(event: MouseEvent) {
  mouseDownInfo.value = { x: event.clientX, y: event.clientY, time: Date.now() }
  linksDisabled.value = false
}

function handleMouseUp(event: MouseEvent) {
  const downInfo = mouseDownInfo.value
  mouseDownInfo.value = null

  const isDrag = !!downInfo && (
    (Date.now() - downInfo.time >= CLICK_TIME_THRESHOLD) ||
    (Math.hypot(event.clientX - downInfo.x, event.clientY - downInfo.y) >= DRAG_DISTANCE_THRESHOLD)
  )

  if (isDrag) {
    handleTextSelection()
    linksDisabled.value = false
    return
  }

  const target = event.target as HTMLElement
  if (target.tagName === 'A' || target.closest('a') || target.classList.contains('internal-link') || target.closest('.internal-link')) {
    linksDisabled.value = false
    return
  }

  if (event.ctrlKey || event.metaKey) {
    pdfStore.closeNotePreviewCard()
    handleCtrlClick(event)
    linksDisabled.value = false
    return
  }

  handleClick(event)
  linksDisabled.value = false
}

function handleClick(event: MouseEvent) {
  const pageEl = findPageElement(event.target as Node)
  if (!pageEl || !pageEl.dataset.page) {
    handleClickOutside(true)
    return
  }

  const pageNumber = Number(pageEl.dataset.page)
  const textLayer = pageEl.querySelector('.textLayer') as HTMLDivElement | null
  if (!textLayer) return

  const layerRect = textLayer.getBoundingClientRect()
  if (!layerRect.width || !layerRect.height) return

  const normalizedX = (event.clientX - layerRect.left) / layerRect.width
  const normalizedY = (event.clientY - layerRect.top) / layerRect.height

  const highlightsAtPoint = pdfStore.getHighlightsAtPoint(pageNumber, normalizedX, normalizedY)

  if (highlightsAtPoint.length === 0) {
    handleClickOutside(true)
    return
  }

  const isSamePoint = highlightsAtCurrentPoint.value.length > 0 &&
    highlightsAtCurrentPoint.value.some(h => highlightsAtPoint.some(hp => hp.id === h.id))

  if (isSamePoint && highlightsAtPoint.length > 1) {
    currentHighlightIndex.value = (currentHighlightIndex.value + 1) % highlightsAtPoint.length
  } else {
    highlightsAtCurrentPoint.value = highlightsAtPoint
    currentHighlightIndex.value = 0
  }

  const selectedHighlight = highlightsAtPoint[currentHighlightIndex.value]
  if (!selectedHighlight) return

  const firstRect = selectedHighlight.rects[0]
  if (!firstRect) return

  const tooltipX = layerRect.left + (firstRect.left + firstRect.width / 2) * layerRect.width
  const tooltipY = layerRect.top + firstRect.top * layerRect.height - 10

  pdfStore.selectHighlight(selectedHighlight, { x: tooltipX, y: tooltipY })
  tooltipPosition.value = { x: tooltipX, y: tooltipY }
  showTooltip.value = true

  window.getSelection()?.removeAllRanges()
}

function handleClickOutside(forceClose: boolean = false) {
  const selection = window.getSelection()
  if (!forceClose && selection && selection.toString().trim()) return

  selection?.removeAllRanges()
  showTooltip.value = false
  pdfStore.clearSelection()
  pdfStore.clearHighlightSelection()
  pdfStore.closeNotePreviewCard()
  highlightsAtCurrentPoint.value = []
  currentHighlightIndex.value = 0
}

function closeTooltip() {
  showTooltip.value = false
  pdfStore.clearSelection()
  pdfStore.clearHighlightSelection()
  highlightsAtCurrentPoint.value = []
  currentHighlightIndex.value = 0
}

function handleParagraphMarkerClick(event: MouseEvent, paragraphId: string, originalText: string) {
  event.stopPropagation()
  event.preventDefault()

  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const panelX = rect.right + 10
  const panelY = rect.top
  const panelWidth = 320
  const finalX = (panelX + panelWidth > window.innerWidth) ? (rect.left - panelWidth - 10) : panelX

  translationStore.openTranslationPanel(paragraphId, { x: Math.max(0, finalX), y: Math.max(0, panelY) }, originalText)
}

// ------------------------- Watch 监听 -------------------------
watch(
  () => pdfStore.currentPdfUrl,
  (url) => {
    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0

    if (url) {
      loadPdf(url)
      loadNotesCache()
    } else {
      cleanup()
      notesCache.value = []
    }
  },
  { immediate: true }
)

watch(
  () => pdfStore.scale,
  () => {
    if (!pendingAnchor.value) {
      setPendingAnchor(captureCenterAnchor())
    }

    isZooming.value = true

    if (preloadAbortController) {
      preloadAbortController.abort()
      preloadAbortController = null
    }

    renderTasks.forEach(task => task.cancel())
    renderTasks.clear()
    pagesNeedingRefresh.clear()
    pageRefs.forEach((_, pageNumber) => pagesNeedingRefresh.add(pageNumber))
    preloadProgress.value = 0

    applyInterimScale()

    nextTick(() => {
      updateVisiblePages()

      if (pendingAnchor.value) {
        nextTick(() => {
          if (pendingAnchor.value) {
            restoreAnchor(pendingAnchor.value)
            clearPendingAnchor()
          }
        })
      }
      settleZooming()
    })
  }
)

let lastUserTriggeredPage = 1
watch(
  () => pdfStore.currentPage,
  (page, oldPage) => {
    if (page !== oldPage && page !== lastUserTriggeredPage) {
      lastUserTriggeredPage = page
      scrollToPage(page, true)
    }
  }
)

watch(
  () => pdfStore.selectedText,
  (newText) => {
    if (!newText) {
      window.getSelection()?.removeAllRanges()
      showTooltip.value = false
    }
  }
)

// 监听内部链接点击事件
window.addEventListener('pdf-internal-link', ((event: CustomEvent<{ 
  destCoords: { page: number; x: number | null; y: number | null; zoom: number | null; type: string }
  clickX: number
  clickY: number 
}>) => {
  const { destCoords, clickX, clickY } = event.detail
  // 显示弹窗而不是直接跳转，弹窗位置在点击位置右侧下方
  const popupX = Math.min(clickX + 10, window.innerWidth - 280)
  const popupY = Math.min(clickY + 10, window.innerHeight - 200)
  pdfStore.openInternalLinkPopup(destCoords, { x: popupX, y: popupY })
  
  // 获取内部链接数据并更新弹窗
  if (pdfStore.currentDocumentId) {
    pdfStore.setInternalLinkLoading(true)
    // 提供 getLinkLayer 函数用于在 valid=0 时搜索段落内的链接
    const getLinkLayer = (page: number) => pageRefs.get(page)?.linkLayer ?? null
    fetchInternalLinkData(pdfStore.currentDocumentId, destCoords, pdfStore.paragraphs, getLinkLayer)
      .then((result) => {
        if (result) {
          pdfStore.setInternalLinkData(result.linkData, result.paragraphContent || undefined)
        } else {
          pdfStore.setInternalLinkData(null, undefined, '获取数据失败')
        }
      })
      .catch((err) => {
        console.error('Failed to fetch internal link data:', err)
        pdfStore.setInternalLinkData(null, undefined, '获取数据失败')
      })
      .finally(() => {
        pdfStore.setInternalLinkLoading(false)
      })
  }
}) as EventListener)

// ------------------------- 生命周期 -------------------------
onMounted(() => {
  nextTick(() => {
    if (!containerRef.value) return

    resizeObserver = new ResizeObserver(() => {
      if (!isResizing.value && pdfDoc.value) {
        isResizing.value = true
      }

      if (resizeTimeout) clearTimeout(resizeTimeout)
      resizeTimeout = setTimeout(() => {
        if (isResizing.value) {
          updateVisiblePages()
          isResizing.value = false
        }
      }, 150)
    })

    resizeObserver.observe(containerRef.value)
  })
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
    resizeTimeout = null
  }
  cleanup()
})
</script>

<template>
  <div class="pdf-viewer-root flex flex-col h-full bg-gray-100 dark:bg-[#0b1220] relative">
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="pdf-scroll-container flex-1 overflow-auto p-4"
      :class="{ 'links-disabled': linksDisabled }"
      @mouseenter="handleMouseEnterContainer"
      @mouseleave="handleMouseLeaveContainer"
      @mousedown="handleMouseDown"
      @mouseup="handleMouseUp"
      @mousemove="handleMouseMove"
      @wheel="handleWheel"
      @scroll="handleScroll"
    >
      <div class="space-y-4 flex flex-col items-center w-fit min-w-full mx-auto">
        <div
          v-for="page in pageNumbers"
          :key="page"
          class="pdf-page relative bg-white dark:bg-[#111827] shadow-lg dark:shadow-[0_10px_30px_rgba(0,0,0,0.45)] outline outline-1 outline-gray-200 dark:outline-[#1f2937] overflow-hidden shrink-0"
          :ref="(el) => handlePageContainerRef(page, el)"
          :data-page="page"
          :style="{
            width: getScaledPageSize(page, pdfStore.scale, pageSizesConstant, pageSizesArray).width + 'px',
            height: getScaledPageSize(page, pdfStore.scale, pageSizesConstant, pageSizesArray).height + 'px'
          }"
        >
          <div
            v-if="!isPageRendered(page)"
            class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 dark:bg-[#0f172a] z-10"
          >
            <div class="loading-spinner mb-3"></div>
            <span class="text-gray-400 text-sm">{{ page }}</span>
          </div>
          <canvas class="absolute top-0 left-0" />
          <div class="highlightLayer absolute inset-0 pointer-events-none" :class="{ 'zooming-layer': isZooming }">
            <template v-for="hl in pdfStore.getHighlightsByPage(page)" :key="hl.id">
              <div
                v-for="(rect, idx) in hl.rects"
                :key="`${hl.id}-${idx}`"
                class="highlight-rect absolute pointer-events-none"
                :style="{
                  left: `${rect.left * 100}%`,
                  top: `${rect.top * 100}%`,
                  width: `${rect.width * 100}%`,
                  height: `${rect.height * 100}%`,
                  backgroundColor: getHighlightColor(hl.color)
                }"
              />
              <div
                v-if="pdfStore.selectedHighlight?.id === hl.id"
                class="highlight-selected-box absolute pointer-events-none"
                :style="getBoundingBoxStyle(hl.rects)"
              />
            </template>
          </div>
          <div class="textLayer absolute inset-0" :class="{ 'zooming-layer': isZooming }" />
          <div class="linkLayer absolute inset-0" :class="{ 'zooming-layer': isZooming }" />
          
          <div class="paragraphMarkerLayer absolute inset-0 pointer-events-none z-10" :class="{ 'zooming-layer': isZooming }">
            <div
              v-for="paragraph in pdfStore.getParagraphsByPage(page)"
              :key="paragraph.id"
              :data-paragraph-id="paragraph.id"
              class="paragraph-marker absolute pointer-events-auto cursor-pointer"
              :style="getParagraphMarkerStyle(paragraph, getPageSize(page, pageSizesConstant, pageSizesArray))"
              @click="handleParagraphMarkerClick($event, paragraph.id, paragraph.content)"
              :title="'点击翻译此段落'"
            >
              <div class="marker-icon">
                <span class="marker-chevron">›</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-else
      class="flex-1 flex flex-col items-center justify-center text-gray-400"
    >
      <svg class="w-24 h-24 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h2 class="text-xl font-medium mb-2">开始阅读</h2>
      <p class="text-sm">从左侧上传 PDF 文件开始您的阅读之旅</p>
    </div>

    <TextSelectionTooltip
      v-if="showTooltip && pdfStore.selectedText"
      :position="tooltipPosition"
      :text="pdfStore.selectedText"
      :mode="pdfStore.isEditingHighlight ? 'highlight' : 'selection'"
      :highlight="pdfStore.selectedHighlight"
      @close="closeTooltip"
    />
    
    <TranslationPanel />
    <NotePreviewCard />
    <InternalLinkPopup />
  </div>
</template>

<style scoped>
.pdf-page {
  border-radius: 0.75rem;
}

.highlightLayer {
  z-index: 4;
  pointer-events: none;
}

.linkLayer {
  z-index: 3;
  pointer-events: none;
}

.links-disabled :deep(.linkLayer),
.links-disabled :deep(.linkLayer a),
.links-disabled :deep(.linkLayer .internal-link) {
  pointer-events: none !important;
}

.highlight-rect {
  background: rgba(255, 235, 59, 0.4);
  border-radius: 4px;
}

.highlight-selected-box {
  border: 2px dashed #4a5568;
  box-shadow: 0 0 4px rgba(0,0,0,0.1);
  background-color: transparent;
  z-index: 2;
}

:deep(.linkLayer a),
:deep(.linkLayer .internal-link) {
  pointer-events: auto;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e5e7eb;
  border-top-color: #6b7280;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.paragraphMarkerLayer {
  z-index: 5;
}

.paragraph-marker {
  z-index: 6;
}

.paragraph-marker .marker-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  transition: all 0.2s ease;
  opacity: 0.5;
}

.paragraph-marker .marker-chevron {
  font-size: 16px;
  font-weight: 600;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  color: rgba(100, 140, 200, 0.8);
  line-height: 1;
  transition: all 0.2s ease;
}

.paragraph-marker:hover .marker-icon {
  opacity: 1;
  transform: scale(1.2) translateX(2px);
}

.paragraph-marker:hover .marker-chevron {
  color: rgba(80, 140, 255, 1);
}

:global(.dark) .paragraph-marker .marker-chevron {
  color: rgba(140, 180, 255, 0.7);
}

:global(.dark) .paragraph-marker:hover .marker-chevron {
  color: rgba(160, 200, 255, 0.95);
}

.zooming-layer {
  pointer-events: none;
  transition: opacity 0.15s ease;
}

:global(.dark .pdf-viewer-root) {
  background: #0b1220;
}

:global(.dark .pdf-scroll-container) {
  background: #0b1220;
}

:global(.dark .pdf-page) {
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}

:global(.dark .pdf-page canvas) {
  background-color: #111827;
  filter: invert(0.92) hue-rotate(180deg) brightness(1.05);
}

:global(.dark .highlight-selected-box) {
  border-color: #cbd5ff;
}

:global(.dark .loading-spinner) {
  border-color: #1f2937;
  border-top-color: #9ca3af;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar) {
  width: 10px;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-track) {
  background: #111827;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-thumb) {
  background: #4b5563;
  border-radius: 6px;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-thumb:hover) {
  background: #6b7280;
}

.textLayer {
  pointer-events: auto;
}

:deep(.textLayer) {
  opacity: 1;
}

:global(.dark .textLayer),
:global(.dark .textLayer span) {
  color: transparent !important;
  mix-blend-mode: normal;
}

:deep(.textLayer span) {
  display: inline-block;
  padding: 5px 0;
  margin: -5px 0;
  line-height: 1.0 !important;
  letter-spacing: 0.2px !important;
  transform-origin: 0 0;
  font-family: "Times New Roman", "Nimbus Roman No9 L", "FreeSerif", "Liberation Serif", serif !important;
  white-space: pre;
  cursor: text;
  color: transparent !important;
}

:deep(.textLayer ::selection) {
  background: rgba(59, 130, 246, 0.3) !important;
}
</style>
