/**
 * PDF 加载管理 Composable
 * 处理 PDF 文档加载、页面尺寸预加载、后台预加载
 */

import { ref } from 'vue'
import { getDocument, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist'
import type { PageSize, PageRef } from '../types/pdf'
import { usePdfStore } from '../stores/pdf'

export interface UsePdfLoaderOptions {
  onLoadComplete?: (pdf: PDFDocumentProxy) => void
  onLoadError?: (error: Error) => void
}

export function usePdfLoader(
  options: UsePdfLoaderOptions = {}
) {
  // PDF 文档实例
  const pdfDoc = ref<PDFDocumentProxy | null>(null)
  
  // 页码列表
  const pageNumbers = ref<number[]>([])
  
  // 页面尺寸相关
  const pageSizesConstant = ref<PageSize | null>(null)
  const pageSizesArray = ref<PageSize[] | null>(null)
  const pageHeightAccumulator = ref<number[]>([])

  // 预加载相关
  const preloadProgress = ref(0)
  const isPreloading = ref(false)
  let preloadAbortController: AbortController | null = null

  // 渲染状态
  const renderTasks = new Map<number, RenderTask>()
  const renderedPages = ref<Set<number>>(new Set())
  const pagesNeedingRefresh = new Set<number>()
  const lastRenderedScale = new Map<number, number>()

  // 页面引用
  const pageRefs = new Map<number, PageRef>()

  /**
   * 加载 PDF 文档并初始化尺寸信息
   */
  async function loadPdf(url: string): Promise<void> {
    cleanup()

    try {
      const loadingTask = getDocument({
        url,
        cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
        cMapPacked: true
      })

      const pdf = await loadingTask.promise
      pdfDoc.value = pdf

      // 预加载所有页面的尺寸信息
      await preloadPageSizes(pdf)

      pageNumbers.value = Array.from({ length: pdf.numPages }, (_, index) => index + 1)

      options.onLoadComplete?.(pdf)
    } catch (error) {
      console.warn('Failed to load PDF:', error)
      options.onLoadError?.(error as Error)
      throw error
    }
  }

  /**
   * 预加载页面尺寸信息
   */
  async function preloadPageSizes(pdf: PDFDocumentProxy): Promise<void> {
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
      pageSizesConstant.value = firstSize
      pageSizesArray.value = null
      pageHeightAccumulator.value = []
    } else {
      pageSizesConstant.value = null
      pageSizesArray.value = tempSizes
      pageHeightAccumulator.value = tempAccumulator
    }

    // 更新到 store，供其他组件使用
    const pdfStore = usePdfStore()
    pdfStore.setPageSizes(pageSizesConstant.value, pageSizesArray.value)
  }

  /**
   * 后台预加载所有页面
   */
  async function startBackgroundPreload(
    renderPageFn: (pageNumber: number) => Promise<void>,
    totalPages: number
  ): Promise<void> {
    if (!pdfDoc.value) return

    if (preloadAbortController) {
      preloadAbortController.abort()
    }
    preloadAbortController = new AbortController()
    const signal = preloadAbortController.signal

    isPreloading.value = true
    preloadProgress.value = 0

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
              if (!signal.aborted) {
                renderPageFn(pageNumber)
              }
              resolve()
            }, { timeout: 100 })
          } else {
            setTimeout(() => {
              if (!signal.aborted) {
                renderPageFn(pageNumber)
              }
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

  /**
   * 清理资源
   */
  function cleanup(): void {
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
    pdfDoc.value = null
  }

  return {
    // 状态
    pdfDoc,
    pageNumbers,
    pageSizesConstant,
    pageSizesArray,
    pageHeightAccumulator,
    preloadProgress,
    isPreloading,
    renderedPages,
    pagesNeedingRefresh,
    lastRenderedScale,
    pageRefs,
    renderTasks,
    // 方法
    loadPdf,
    startBackgroundPreload,
    cleanup
  }
}
