/**
 * PDF 渲染 Composable
 * 处理页面渲染、文本层、链接层、后台预加载等
 */

import { ref, nextTick, type Ref, shallowRef } from 'vue'
import { renderTextLayer, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist'
import type { PageRef, PageSize } from '../types/pdf'
import type { PageGeometry } from './usePageGeometry'
import { appendLinkOverlay, appendInternalLinkOverlay } from '../utils/pdfHelpers'

export interface RenderOptions {
  preserveContent?: boolean
}

export function usePdfRender(
  containerRef: Ref<HTMLElement | null>,
  pdfDoc: Ref<PDFDocumentProxy | null>,
  pageRefs: Map<number, PageRef>,
  pageNumbers: Ref<number[]>,
  geometry: PageGeometry,
  scale: Ref<number>,
  isZooming: Ref<boolean>,
  onPageRendered?: (pageNumber: number) => void
) {
  // 渲染相关状态
  const renderTasks = new Map<number, RenderTask>()
  const renderedPages = ref<Set<number>>(new Set())
  const pagesNeedingRefresh = new Set<number>()
  const lastRenderedScale = new Map<number, number>()
  const visiblePages = new Set<number>()

  // 预加载相关
  const preloadProgress = ref(0)
  const isPreloading = ref(false)
  const preloadAbortController = shallowRef<AbortController | null>(null)

  // 页面是否已渲染
  function isPageRendered(pageNumber: number): boolean {
    return renderedPages.value.has(pageNumber)
  }

  // 渲染 Link Layer
  async function renderLinkLayer(
    annotations: any[],
    viewport: any,
    container: HTMLElement,
    onInternalLinkClick?: (page: number) => void
  ): Promise<void> {
    container.innerHTML = ''

    for (const annotation of annotations) {
      if (annotation.subtype !== 'Link') continue

      const rect = viewport.convertToViewportRectangle(annotation.rect)
      const [x1, y1, x2, y2] = rect
      const overlayRect = {
        left: Math.min(x1, x2),
        top: Math.min(y1, y2),
        width: Math.abs(x2 - x1),
        height: Math.abs(y2 - y1)
      }

      if (annotation.url) {
        appendLinkOverlay(container, overlayRect, annotation.url, annotation.url || 'External Link')
      } else if (annotation.dest) {
        const destPage = await resolveDestination(annotation.dest)
        if (destPage) {
          appendInternalLinkOverlay(
            container,
            overlayRect,
            destPage,
            `跳转到第 ${destPage} 页`,
            onInternalLinkClick
          )
        }
      } else if (annotation.action?.dest) {
        const destPage = await resolveDestination(annotation.action.dest)
        if (destPage) {
          appendInternalLinkOverlay(
            container,
            overlayRect,
            destPage,
            `跳转到第 ${destPage} 页`,
            onInternalLinkClick
          )
        }
      }
    }
  }

  // 内部链接解析
  async function resolveDestination(dest: any): Promise<number | null> {
    if (!pdfDoc.value) return null

    try {
      let destArray = dest

      if (typeof dest === 'string') {
        destArray = await pdfDoc.value.getDestination(dest)
      }

      if (!destArray || !Array.isArray(destArray)) return null

      const pageRef = destArray[0]
      if (!pageRef) return null

      const pageIndex = await pdfDoc.value.getPageIndex(pageRef)
      return pageIndex + 1

    } catch (err) {
      console.error('Error resolving destination:', err)
      return null
    }
  }

  // 核心渲染逻辑：渲染页面
  async function renderPage(pageNumber: number, options?: RenderOptions): Promise<void> {
    const pdf = pdfDoc.value
    const refs = pageRefs.get(pageNumber)
    if (!pdf || !refs) return

    if (renderTasks.has(pageNumber)) return

    const preserveContent = !!options?.preserveContent && renderedPages.value.has(pageNumber)

    const page = await pdf.getPage(pageNumber)

    const targetCanvas = preserveContent
      ? document.createElement('canvas')
      : refs.canvas

    const context = targetCanvas.getContext('2d', {
      alpha: false,
      willReadFrequently: false
    })
    if (!context) return

    const outputScale = window.devicePixelRatio || 1
    const cssViewport = page.getViewport({ scale: scale.value })
    const renderViewport = page.getViewport({ scale: scale.value * outputScale })

    const scaledSize = geometry.getScaledPageSize(pageNumber)
    const displayWidth = scaledSize.width
    const displayHeight = scaledSize.height

    refs.container.style.width = `${displayWidth}px`
    refs.container.style.height = `${displayHeight}px`

    targetCanvas.width = Math.floor(renderViewport.width)
    targetCanvas.height = Math.floor(renderViewport.height)
    targetCanvas.style.width = `${displayWidth}px`
    targetCanvas.style.height = `${displayHeight}px`

    refs.textLayer.style.width = `${displayWidth}px`
    refs.textLayer.style.height = `${displayHeight}px`
    refs.textLayer.style.setProperty('--scale-factor', `${cssViewport.scale}`)
    refs.textLayer.style.transform = 'scale(1)'
    refs.textLayer.style.transformOrigin = 'top left'
    refs.textLayer.innerHTML = ''

    refs.linkLayer.style.width = `${displayWidth}px`
    refs.linkLayer.style.height = `${displayHeight}px`
    refs.linkLayer.style.transform = 'scale(1)'
    refs.linkLayer.style.transformOrigin = 'top left'

    refs.highlightLayer.style.width = `${displayWidth}px`
    refs.highlightLayer.style.height = `${displayHeight}px`
    refs.highlightLayer.style.transform = 'scale(1)'
    refs.highlightLayer.style.transformOrigin = 'top left'

    const renderTask = page.render({
      canvasContext: context,
      viewport: renderViewport
    })
    renderTasks.set(pageNumber, renderTask)

    try {
      await renderTask.promise
    } catch (err: any) {
      if (err.name === 'RenderingCancelledException') {
        return
      }
      console.error(err)
    }

    const textContent = await page.getTextContent()
    const textDivs: HTMLElement[] = []
    await renderTextLayer({
      textContentSource: textContent,
      container: refs.textLayer,
      viewport: cssViewport,
      textDivs
    }).promise

    // 修复：强制调整文字宽度以对齐 PDF 原始内容
    if (textContent && textContent.items && textDivs.length === textContent.items.length) {
      const items = textContent.items as any[]
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        const div = textDivs[i]

        if (!item.str || !item.width || !div) continue

        const targetWidth = item.width * cssViewport.scale
        const rect = div.getBoundingClientRect()

        const transform = item.transform
        const isVertical = transform && Math.abs(transform[0]) < 1e-3 && Math.abs(transform[3]) < 1e-3
        const isHorizontal = !transform || (Math.abs(transform[1]) < 1e-3 && Math.abs(transform[2]) < 1e-3)

        let currentLength = 0
        if (isVertical) {
          currentLength = rect.height
        } else if (isHorizontal) {
          currentLength = rect.width
        } else {
          continue
        }

        if (currentLength > 0) {
          const scaleFactor = targetWidth / currentLength
          if (Math.abs(scaleFactor - 1) > 0.01) {
            const existingTransform = div.style.transform || ''
            div.style.transform = `${existingTransform} scaleX(${scaleFactor})`
          }
        }
      }
    }

    try {
      const annotations = await page.getAnnotations()
      await renderLinkLayer(annotations, cssViewport, refs.linkLayer)
    } catch (err) {
      console.error('Error rendering Link Layer :', err)
    }

    if (preserveContent) {
      const destContext = refs.canvas.getContext('2d', {
        alpha: false,
        willReadFrequently: false
      })
      if (destContext) {
        refs.canvas.width = targetCanvas.width
        refs.canvas.height = targetCanvas.height
        refs.canvas.style.width = targetCanvas.style.width
        refs.canvas.style.height = targetCanvas.style.height
        destContext.clearRect(0, 0, refs.canvas.width, refs.canvas.height)
        destContext.drawImage(targetCanvas, 0, 0)
      }
    }

    lastRenderedScale.set(pageNumber, scale.value)
    renderedPages.value = new Set([...renderedPages.value, pageNumber])

    if (onPageRendered) {
      onPageRendered(pageNumber)
    }
  }

  // 后台预加载所有页面
  async function startBackgroundPreload(): Promise<void> {
    const pdf = pdfDoc.value
    if (!pdf) return

    if (preloadAbortController.value) {
      preloadAbortController.value.abort()
    }
    preloadAbortController.value = new AbortController()
    const signal = preloadAbortController.value.signal

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
              if (!signal.aborted) {
                renderPage(pageNumber)
              }
              resolve()
            }, { timeout: 100 })
          } else {
            setTimeout(() => {
              if (!signal.aborted) {
                renderPage(pageNumber)
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

  // 取消所有渲染任务
  function cancelAllRenderTasks(): void {
    renderTasks.forEach(task => task.cancel())
    renderTasks.clear()
  }

  // 清理
  function cleanup(): void {
    if (preloadAbortController.value) {
      preloadAbortController.value.abort()
      preloadAbortController.value = null
    }
    isPreloading.value = false
    preloadProgress.value = 0

    cancelAllRenderTasks()
    renderedPages.value = new Set()
    pagesNeedingRefresh.clear()
    lastRenderedScale.clear()
    visiblePages.clear()
  }

  // 标记页面需要刷新
  function markPagesForRefresh(): void {
    pageRefs.forEach((_, pageNumber) => pagesNeedingRefresh.add(pageNumber))
  }

  return {
    renderTasks,
    renderedPages,
    pagesNeedingRefresh,
    lastRenderedScale,
    visiblePages,
    preloadProgress,
    isPreloading,
    preloadAbortController,
    isPageRendered,
    renderPage,
    renderLinkLayer,
    resolveDestination,
    startBackgroundPreload,
    cancelAllRenderTasks,
    markPagesForRefresh,
    cleanup
  }
}

export type PdfRenderManager = ReturnType<typeof usePdfRender>
