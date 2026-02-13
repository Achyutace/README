/**
 * PDF 页面渲染 Composable
 * 处理页面渲染、可见区域检测、Link Layer 渲染
 */

import { nextTick } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { renderTextLayer, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist'
import type { Ref } from 'vue'
import type { PageRef, RenderPageOptions, PageSize } from '../types/pdf'
import { getPageAtY, getScaledPageSize, getPageSize } from '../utils/PdfHelper'
import { renderLinkLayer, fixTextLayerWidth, applyInterimScaleToPage } from '../utils/PdfRender'

export interface UsePageRenderOptions {
  buffer?: number
  onPageRendered?: (pageNumber: number) => void
}

export function usePageRender(
  containerRef: Ref<HTMLElement | null>,
  pdfDoc: Ref<PDFDocumentProxy | null>,
  pageNumbers: Ref<number[]>,
  pageRefs: Map<number, PageRef>,
  renderTasks: Map<number, RenderTask>,
  renderedPages: Ref<Set<number>>,
  pagesNeedingRefresh: Set<number>,
  lastRenderedScale: Map<number, number>,
  pageSizesConstant: Ref<PageSize | null>,
  pageSizesArray: Ref<PageSize[] | null>,
  pageHeightAccumulator: Ref<number[]>,
  scale: Ref<number>,
  isZooming: Ref<boolean>,
  composableOptions: UsePageRenderOptions = {}
) {
  const { buffer = 500 } = composableOptions
  const visiblePages = new Set<number>()

  /**
   * 核心渲染逻辑：仅渲染可见区域页面
   */
  const updateVisiblePages = useDebounceFn(() => {
    if (!containerRef.value || !pdfDoc.value) return

    const container = containerRef.value
    const scrollTop = container.scrollTop
    const clientHeight = container.clientHeight

    const startY = Math.max(0, scrollTop - buffer)
    const endY = scrollTop + clientHeight + buffer

    const startPage = getPageAtY(
      startY,
      pageNumbers.value.length,
      scale.value,
      pageSizesConstant.value,
      pageHeightAccumulator.value
    )
    const endPage = getPageAtY(
      endY,
      pageNumbers.value.length,
      scale.value,
      pageSizesConstant.value,
      pageHeightAccumulator.value
    )

    const newVisiblePages = new Set<number>()

    for (let p = startPage; p <= endPage; p++) {
      if (p > pageNumbers.value.length) break
      newVisiblePages.add(p)

      const alreadyRendered = renderedPages.value.has(p)
      const needsRefresh = pagesNeedingRefresh.has(p)
      const shouldRenderNow = !alreadyRendered || (!isZooming.value && needsRefresh)

      if (shouldRenderNow && !renderTasks.has(p)) {
        renderPage(p, { preserveContent: alreadyRendered })
        pagesNeedingRefresh.delete(p)
      }
    }

    visiblePages.clear()
    newVisiblePages.forEach(p => visiblePages.add(p))
  }, 100)

  /**
   * 渲染单个页面
   */
  async function renderPage(pageNumber: number, options?: RenderPageOptions): Promise<void> {
    const pdf = pdfDoc.value
    const refs = pageRefs.get(pageNumber)
    if (!pdf || !refs) {
      if (!pdf) console.warn(`Cannot render page ${pageNumber}: PDF document not loaded`)
      if (!refs) console.warn(`Cannot render page ${pageNumber}: page refs not found`)
      return
    }

    if (renderTasks.has(pageNumber)) {
      console.warn(`Render task already in progress for page ${pageNumber}`)
      return
    }

    const preserveContent = !!options?.preserveContent && renderedPages.value.has(pageNumber)

    // 记录渲染开始时的 scale，用于后续检查 scale 是否已变化
    const renderStartScale = scale.value

    const page = await pdf.getPage(pageNumber)

    const targetCanvas = preserveContent
      ? document.createElement('canvas')
      : refs.canvas

    const context = targetCanvas.getContext('2d', {
      alpha: false,
      willReadFrequently: false
    })
    if (!context) {
      console.warn(`Failed to get 2D context for page ${pageNumber} canvas`)
      return
    }

    const outputScale = window.devicePixelRatio || 1
    const cssViewport = page.getViewport({ scale: scale.value })
    const renderViewport = page.getViewport({ scale: scale.value * outputScale })

    const scaledSize = getScaledPageSize(
      pageNumber,
      scale.value,
      pageSizesConstant.value,
      pageSizesArray.value
    )
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

    fixTextLayerWidth(textContent, textDivs, cssViewport)

    try {
      const annotations = await page.getAnnotations()
      await renderLinkLayer(
        annotations,
        cssViewport,
        refs.linkLayer,
        pdf,
        (destCoords, clickX, clickY) => {
          // 内部链接点击 - 通过事件通知外部处理，传递目标坐标和点击位置
          const event = new CustomEvent('pdf-internal-link', { 
            detail: { destCoords, clickX, clickY } 
          })
          window.dispatchEvent(event)
        },
        (destCoords) => {
          // 直接跳转到目标位置（table, section, figure, appendix 等）
          scrollToPage(destCoords.page, true)
        }
      )
    } catch (err) {
      console.error('Error rendering Link Layer:', err)
    }

    // 检查 scale 是否在渲染过程中已变化，如果变化则跳过样式更新
    // 避免过时的渲染结果覆盖当前正确的 canvas 尺寸
    if (scale.value !== renderStartScale) {
      renderTasks.delete(pageNumber)
      return
    }

    if (preserveContent) {
      const destContext = refs.canvas.getContext('2d', { alpha: false, willReadFrequently: false })
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
    renderTasks.delete(pageNumber)

    if (composableOptions?.onPageRendered) {
      composableOptions.onPageRendered(pageNumber)
    }
  }

  /**
   * 应用过渡缩放效果
   */
  function applyInterimScale(): void {
    pageRefs.forEach((refs, pageNumber) => {
      const size = getPageSize(
        pageNumber,
        pageSizesConstant.value,
        null
      )
      if (!size) return

      applyInterimScaleToPage(
        refs,
        pageNumber,
        scale.value,
        lastRenderedScale.get(pageNumber),
        size
      )
    })
  }

  /**
   * 滚动到指定页面
   */
  function scrollToPage(page: number, instant: boolean = false): void {
    if (!containerRef.value) return
    const refs = pageRefs.get(page)
    const behavior = instant ? 'instant' : 'smooth'

    if (refs) {
      containerRef.value.scrollTo({
        top: Math.round(refs.container.offsetTop - 12),
        behavior: behavior as ScrollBehavior
      })
      return
    }

    nextTick(() => {
      const retryRefs = pageRefs.get(page)
      if (retryRefs && containerRef.value) {
        containerRef.value.scrollTo({
          top: Math.round(retryRefs.container.offsetTop - 12),
          behavior: behavior as ScrollBehavior
        })
      }
    })
  }

  return {
    visiblePages,
    updateVisiblePages,
    renderPage,
    applyInterimScale,
    scrollToPage
  }
}
