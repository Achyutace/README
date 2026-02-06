<script setup lang="ts">
/*
----------------------------------------------------------------------
                            Pdf 查看器组件
----------------------------------------------------------------------
*/

// ------------------------- 导入依赖与组件 -------------------------
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch, computed } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
} from 'pdfjs-dist'
import 'pdfjs-dist/web/pdf_viewer.css'

// 引入 pdf.js worker
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.js?url'
import { usePdfStore } from '../../stores/pdf'
import { useLibraryStore } from '../../stores/library'

// 子组件
import TextSelectionTooltip from './TextSelectionTooltip.vue'
import TranslationPanelMulti from './TranslationPanelMulti.vue'
import NotePreviewCard from './NotePreviewCard.vue'

// Composables
import { usePageGeometry } from './composables/usePageGeometry'
import { usePdfRender } from './composables/usePdfRender'
import { useZoom } from './composables/useZoom'
import { useInteractions } from './composables/useInteractions'
import { useTextSelection } from './composables/useTextSelection'
import { useNotesCache } from './composables/useNotesCache'

// 工具函数
import {
  getHighlightColor,
  getBoundingBoxStyle
} from './utils/pdfHelpers'
import type { PageRef, PageSize } from './types/pdf'

GlobalWorkerOptions.workerSrc = pdfWorker

// ------------------------- 初始化 store 实例 -------------------------
const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

// ------------------------- 初始化 PDF 状态与引用 -------------------------
const containerRef = ref<HTMLElement | null>(null)
const pdfDoc = shallowRef<PDFDocumentProxy | null>(null)
const pageNumbers = ref<number[]>([])
const pageRefs = new Map<number, PageRef>()

// ------------------------- 初始化 Composables -------------------------
// 创建 scale 的响应式引用
const scaleRef = computed(() => pdfStore.scale)
const totalPagesRef = computed(() => pdfStore.totalPages)

// 页面几何计算
const geometry = usePageGeometry(scaleRef)

// 缩放管理（先声明，因为 render 需要用到 zoom.isZooming）
const zoom = useZoom(
  containerRef,
  pageRefs,
  pageNumbers,
  geometry,
  scaleRef
)

// PDF 渲染
const render = usePdfRender(
  containerRef,
  pdfDoc,
  pageRefs,
  pageNumbers,
  geometry,
  scaleRef,
  zoom.isZooming,
  () => {}
)

// 交互处理
const interactions = useInteractions(
  containerRef,
  pageRefs,
  geometry,
  scaleRef,
  totalPagesRef,
  {
    onScroll: (page) => {
      pdfStore.goToPage(page)
    },
    onTextSelection: () => {
      textSelection.handleTextSelection()
    },
    onZoom: (nextScale, mousePos) => {
      if (mousePos) {
        zoom.setPendingAnchor(zoom.captureCenterAnchor(mousePos))
      } else {
        zoom.setPendingAnchor(zoom.captureCenterAnchor())
      }
      pdfStore.setScale(nextScale)
    },
    onClick: (event) => {
      handleClick(event)
    },
    onUpdateVisiblePages: () => {
      updateVisiblePages()
    },
    onStartBackgroundPreload: () => {
      render.startBackgroundPreload()
    }
  }
)

// 文本选择
const textSelection = useTextSelection({
  onSelectText: (text, position, selectionInfo) => {
    pdfStore.setSelectedText(text, position)
    pdfStore.setSelectionInfo(selectionInfo)
  },
  onSelectHighlight: (highlight, position) => {
    pdfStore.selectHighlight(highlight, position)
  },
  onClearSelection: () => {
    pdfStore.clearSelection()
    pdfStore.clearHighlightSelection()
    pdfStore.closeNotePreviewCard()
  },
  getHighlightsAtPoint: (page, x, y) => {
    return pdfStore.getHighlightsAtPoint(page, x, y)
  }
})

// 笔记缓存
const notesCache = useNotesCache({
  getCurrentDocumentId: () => libraryStore.currentDocument?.id,
  onOpenNotePreview: (note, position) => {
    pdfStore.openNotePreviewCard(note, position)
  },
  onCloseNotePreview: () => {
    pdfStore.closeNotePreviewCard()
  }
})

// ------------------------- 可见页面更新 -------------------------
const updateVisiblePages = useDebounceFn(() => {
  if (!containerRef.value || !pdfDoc.value) return

  const container = containerRef.value
  const scrollTop = container.scrollTop
  const clientHeight = container.clientHeight
  const buffer = 500

  const startY = Math.max(0, scrollTop - buffer)
  const endY = scrollTop + clientHeight + buffer

  const startPage = geometry.getPageAtY(startY, pageNumbers.value.length)
  const endPage = geometry.getPageAtY(endY, pageNumbers.value.length)

  const newVisiblePages = new Set<number>()

  for (let p = startPage; p <= endPage; p++) {
    if (p > pdfStore.totalPages) break
    newVisiblePages.add(p)

    const alreadyRendered = render.renderedPages.value.has(p)
    const needsRefresh = render.pagesNeedingRefresh.has(p)
    const shouldRenderNow = !alreadyRendered || (!zoom.isZooming.value && needsRefresh)

    if (shouldRenderNow && !render.renderTasks.has(p)) {
      render.renderPage(p, { preserveContent: alreadyRendered })
      render.pagesNeedingRefresh.delete(p)
    }
  }

  render.visiblePages.clear()
  newVisiblePages.forEach(p => render.visiblePages.add(p))
}, 100)

// ------------------------- 引用处理与资源管理 -------------------------
function handlePageContainerRef(
  pageNumber: number,
  ref: any,
  _refs?: Record<string, any>
) {
  const el = ref instanceof HTMLElement ? ref : null
  setPageRef(pageNumber, el)
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
  }
}

// ------------------------- 缩放防抖处理 -------------------------
const settleZooming = useDebounceFn(() => {
  zoom.setZooming(false)
  updateVisiblePages()
  render.startBackgroundPreload()
}, 180)

// ------------------------- PDF 文档加载 -------------------------
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

  // 预加载所有页面的尺寸信息
  const tempSizes: PageSize[] = []
  let allSameSize = true
  let firstSize: PageSize | null = null

  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i)
    const viewport = page.getViewport({ scale: 1 })
    const size = { width: viewport.width, height: viewport.height }

    if (i === 1) {
      firstSize = size
    } else if (firstSize) {
      if (Math.abs(size.width - firstSize.width) > 1 || Math.abs(size.height - firstSize.height) > 1) {
        allSameSize = false
      }
    }

    tempSizes.push(size)
  }

  geometry.setPageSizes(tempSizes, allSameSize)
  pageNumbers.value = Array.from({ length: pdf.numPages }, (_, index) => index + 1)

  pdfStore.isLoading = false
  await nextTick()

  updateVisiblePages()

  setTimeout(() => {
    render.startBackgroundPreload()
  }, 500)
}

// ------------------------- 清理函数 -------------------------
function cleanup() {
  render.cleanup()
  geometry.cleanup()
  zoom.setZooming(false)
  zoom.setPendingAnchor(null)
  pageRefs.clear()
  pageNumbers.value = []
  pdfDoc.value = null
}

// ------------------------- 点击处理 -------------------------
function handleClick(event: MouseEvent) {
  // Ctrl+点击：查找笔记
  if (event.ctrlKey || event.metaKey) {
    notesCache.handleCtrlClick(event)
    return
  }

  // 普通点击处理高亮
  textSelection.handleHighlightClick(event)
}

// ------------------------- 段落翻译 -------------------------
function handleParagraphMarkerClick(event: MouseEvent, paragraphId: string, originalText: string) {
  event.stopPropagation()
  event.preventDefault()

  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()

  const panelX = rect.right + 10
  const panelY = rect.top

  const panelWidth = 320
  const finalX = (panelX + panelWidth > window.innerWidth) ? (rect.left - panelWidth - 10) : panelX

  pdfStore.openTranslationPanel(paragraphId, { x: Math.max(0, finalX), y: Math.max(0, panelY) }, originalText)
}

// 计算段落光标在页面中的位置
function getParagraphMarkerStyle(paragraph: { bbox: { x0: number; y0: number } }, pageNumber: number) {
  const size = geometry.getPageSize(pageNumber)
  if (!size) return { display: 'none' }

  const left = (paragraph.bbox.x0 / size.width) * 100
  const top = (paragraph.bbox.y0 / size.height) * 100

  return {
    left: `${left}%`,
    top: `${top}%`,
    transform: 'translate(-100%, -50%)'
  }
}

// ------------------------- Watchers -------------------------
// 监听当前 PDF 地址的变化
watch(
  () => pdfStore.currentPdfUrl,
  (url) => {
    textSelection.closeTooltip()
    textSelection.highlightsAtCurrentPoint.value = []
    textSelection.currentHighlightIndex.value = 0

    if (url) {
      loadPdf(url)
      notesCache.loadNotesCache()
    } else {
      console.log('No PDF URL provided.')
      cleanup()
      notesCache.cleanup()
    }
  },
  { immediate: true }
)

// 监听缩放比例变化
watch(
  () => pdfStore.scale,
  () => {
    if (!zoom.pendingAnchor.value) {
      zoom.setPendingAnchor(zoom.captureCenterAnchor())
    }

    zoom.setZooming(true)

    if (render.preloadAbortController.value) {
      render.preloadAbortController.value.abort()
    }

    render.cancelAllRenderTasks()
    render.pagesNeedingRefresh.clear()
    render.markPagesForRefresh()
    render.preloadProgress.value = 0

    zoom.applyInterimScale(render.lastRenderedScale)

    nextTick(() => {
      updateVisiblePages()

      if (zoom.pendingAnchor.value) {
        nextTick(() => {
          if (zoom.pendingAnchor.value) {
            zoom.restoreAnchor(zoom.pendingAnchor.value)
            zoom.setPendingAnchor(null)
          }
        })
      }
      settleZooming()
    })
  }
)

// 监听工具栏触发的页面跳转
watch(
  () => pdfStore.currentPage,
  (page, oldPage) => {
    if (page !== oldPage && page !== interactions.lastUserTriggeredPage.value) {
      interactions.setLastUserTriggeredPage(page)
      interactions.scrollToPage(page, true)
    }
  }
)

// 监听选区清除
watch(
  () => pdfStore.selectedText,
  (newText) => {
    if (!newText) {
      window.getSelection()?.removeAllRanges()
      textSelection.showTooltip.value = false
    }
  }
)

// ------------------------- 生命周期 -------------------------
onMounted(() => {
  nextTick(() => {
    interactions.setupResizeObserver(() => {
      updateVisiblePages()
    })
  })
})

onBeforeUnmount(() => {
  interactions.cleanupResizeObserver()
  cleanup()
  notesCache.cleanup()
})
</script>

<template>
  <!-- 组件根容器，纵向排列，占满可用高度 -->
  <div class="pdf-viewer-root flex flex-col h-full bg-gray-100 dark:bg-[#0b1220] relative">
    <!-- 主内容区，显示 PDF 页面的滚动容器 -->
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="pdf-scroll-container flex-1 overflow-auto p-4"
      :class="{ 'links-disabled': interactions.linksDisabled.value }"
      @mouseenter="interactions.handleMouseEnterContainer"
      @mouseleave="interactions.handleMouseLeaveContainer"
      @mousedown="interactions.handleMouseDown"
      @mouseup="interactions.handleMouseUp"
      @mousemove="interactions.handleMouseMove"
      @wheel="interactions.handleWheel"
      @scroll="interactions.handleScroll"
    >
      <!-- 居中内容区，控制最大宽度与行间距 -->
      <div class="space-y-4 flex flex-col items-center w-fit min-w-full mx-auto">
        <!-- 遍历所有页码生成页面容器 -->
        <div
          v-for="page in pageNumbers"
          :key="page"
          class="pdf-page relative bg-white dark:bg-[#111827] shadow-lg dark:shadow-[0_10px_30px_rgba(0,0,0,0.45)] outline outline-1 outline-gray-200 dark:outline-[#1f2937] overflow-hidden shrink-0"
          :ref="(el, refs) => handlePageContainerRef(page, el, refs)"
          :data-page="page"
          :style="{
            width: geometry.getScaledPageSize(page).width + 'px',
            height: geometry.getScaledPageSize(page).height + 'px'
          }"
        >
          <!-- 加载中占位符 -->
          <div
            v-if="!render.isPageRendered(page)"
            class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 dark:bg-[#0f172a] z-10"
          >
            <div class="loading-spinner mb-3"></div>
            <span class="text-gray-400 text-sm">{{ page }}</span>
          </div>
          <canvas class="absolute top-0 left-0" />
          <div class="highlightLayer absolute inset-0 pointer-events-none" :class="{ 'zooming-layer': zoom.isZooming.value }">
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
              <!-- 选中的高亮显示整体外包框 -->
              <div
                v-if="pdfStore.selectedHighlight?.id === hl.id"
                class="highlight-selected-box absolute pointer-events-none"
                :style="getBoundingBoxStyle(hl.rects)"
              />
            </template>
          </div>
          <div class="textLayer absolute inset-0" :class="{ 'zooming-layer': zoom.isZooming.value }" />
          <div class="linkLayer absolute inset-0" :class="{ 'zooming-layer': zoom.isZooming.value }" />

          <!-- 段落光标层 -->
          <div class="paragraphMarkerLayer absolute inset-0 pointer-events-none z-10" :class="{ 'zooming-layer': zoom.isZooming.value }">
            <div
              v-for="paragraph in pdfStore.getParagraphsByPage(page)"
              :key="paragraph.id"
              :data-paragraph-id="paragraph.id"
              class="paragraph-marker absolute pointer-events-auto cursor-pointer"
              :style="getParagraphMarkerStyle(paragraph, page)"
              @click="handleParagraphMarkerClick($event, paragraph.id, paragraph.content)"
              :title="'点击翻译此段落'"
            >
              <!-- 极简小光标：小矩形指示器 -->
              <div class="marker-icon">
                <span class="marker-chevron">›</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 当没有选择 PDF 时的占位提示 -->
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

    <!-- 文字选中后的工具提示组件 -->
    <TextSelectionTooltip
      v-if="textSelection.showTooltip.value && pdfStore.selectedText"
      :position="textSelection.tooltipPosition.value"
      :text="pdfStore.selectedText"
      :mode="pdfStore.isEditingHighlight ? 'highlight' : 'selection'"
      :highlight="pdfStore.selectedHighlight"
      @close="textSelection.closeTooltip"
    />

    <!-- 多窗口翻译面板（可拖动，位于最上层） -->
    <TranslationPanelMulti />

    <!-- 笔记预览卡片（Ctrl+点击触发） -->
    <NotePreviewCard />
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

/* 加载动画 */
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

/* 段落光标层 */
.paragraphMarkerLayer {
  z-index: 5;
}

/* 段落光标样式 - 发光 > 符号 */
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

/* 夜间模式段落光标 */
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

/* Dark mode adjustments: dark canvas and white text for comfortable reading */
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

/* Dark mode scrollbar for the PDF scroller */
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

/* Fix for PDF text layer alignment and font matching (ICML / Times New Roman) */
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
