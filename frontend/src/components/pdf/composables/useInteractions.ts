/**
 * 交互处理 Composable
 * 处理滚动、鼠标事件、滚轮缩放等
 */

import { ref, type Ref, readonly } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type { PageRef, MouseDownInfo } from '../types/pdf'
import type { PageGeometry } from './usePageGeometry'
import { CLICK_TIME_THRESHOLD, DRAG_DISTANCE_THRESHOLD } from '../utils/pdfHelpers'

export interface InteractionsOptions {
  onScroll?: (page: number) => void
  onTextSelection?: () => void
  onZoom?: (delta: number, mousePos?: { x: number; y: number }) => void
  onClick?: (event: MouseEvent, isDrag: boolean) => void
  onUpdateVisiblePages?: () => void
  onStartBackgroundPreload?: () => void
}

export function useInteractions(
  containerRef: Ref<HTMLElement | null>,
  pageRefs: Map<number, PageRef>,
  geometry: PageGeometry,
  scale: Ref<number>,
  totalPages: Ref<number>,
  options: InteractionsOptions = {}
) {
  // 状态
  const isPointerOverPdf = ref(false)
  const linksDisabled = ref(false)
  const isResizing = ref(false)
  const mouseDownInfo = ref<MouseDownInfo | null>(null)

  let resizeObserver: ResizeObserver | null = null
  let resizeTimeout: ReturnType<typeof setTimeout> | null = null

  // 最后用户触发的页面（用于防止循环更新）
  const lastUserTriggeredPage = ref(1)

  // 鼠标进入 PDF 框
  function handleMouseEnterContainer(): void {
    isPointerOverPdf.value = true
  }

  // 鼠标离开 PDF 框
  function handleMouseLeaveContainer(): void {
    isPointerOverPdf.value = false
    linksDisabled.value = false
  }

  // 滚动处理
  const handleScroll = useDebounceFn(() => {
    if (!containerRef.value) return

    if (options.onUpdateVisiblePages) {
      options.onUpdateVisiblePages()
    }

    const scrollTop = containerRef.value.scrollTop
    const p = geometry.getPageAtY(scrollTop, totalPages.value)

    let nearestPage = p
    let minDistance = Math.abs(geometry.getPageTop(p) - scrollTop)

    if (p < totalPages.value) {
      const nextP = p + 1
      const distNext = Math.abs(geometry.getPageTop(nextP) - scrollTop)
      if (distNext < minDistance) {
        nearestPage = nextP
      }
    }

    if (nearestPage !== lastUserTriggeredPage.value && nearestPage <= totalPages.value) {
      lastUserTriggeredPage.value = nearestPage
      if (options.onScroll) {
        options.onScroll(nearestPage)
      }
    }
  }, 50)

  // 水平划动 + 缩放 PDF
  function handleWheel(event: WheelEvent): void {
    if (!isPointerOverPdf.value) return

    const container = containerRef.value
    if (!container) return

    // 缩放 PDF：Ctrl + 滚轮
    if (event.ctrlKey) {
      event.preventDefault()
      event.stopPropagation()

      const isHorizontalOverflow = container.scrollWidth > container.clientWidth + 1

      let mousePos: { x: number; y: number } | undefined
      if (isHorizontalOverflow) {
        mousePos = { x: event.clientX, y: event.clientY }
      }

      const delta = event.deltaY
      const step = Math.min(0.25, Math.max(0.05, Math.abs(delta) / 100))
      const nextScale = delta < 0 ? scale.value + step : scale.value - step

      if (options.onZoom) {
        options.onZoom(nextScale, mousePos)
      }
      return
    }

    // 水平划动处理
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

  // 鼠标按下
  function handleMouseDown(event: MouseEvent): void {
    mouseDownInfo.value = {
      x: event.clientX,
      y: event.clientY,
      time: Date.now()
    }
    linksDisabled.value = false
  }

  // 鼠标移动
  function handleMouseMove(event: MouseEvent): void {
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

  // 鼠标抬起
  function handleMouseUp(event: MouseEvent): void {
    const downInfo = mouseDownInfo.value
    mouseDownInfo.value = null

    const isDrag = !!downInfo && (
      (Date.now() - downInfo.time >= CLICK_TIME_THRESHOLD) ||
      (Math.hypot(event.clientX - downInfo.x, event.clientY - downInfo.y) >= DRAG_DISTANCE_THRESHOLD)
    )

    if (isDrag) {
      if (options.onTextSelection) {
        options.onTextSelection()
      }
      linksDisabled.value = false
      return
    }

    // 检查是否点击在链接上
    const target = event.target as HTMLElement
    if (target.tagName === 'A' || target.closest('a') || target.classList.contains('internal-link') || target.closest('.internal-link')) {
      linksDisabled.value = false
      return
    }

    if (options.onClick) {
      options.onClick(event, false)
    }
    linksDisabled.value = false
  }

  // 跳转到指定页面
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

    // 重试
    setTimeout(() => {
      const retryRefs = pageRefs.get(page)
      if (retryRefs && containerRef.value) {
        containerRef.value.scrollTo({
          top: Math.round(retryRefs.container.offsetTop - 12),
          behavior: behavior as ScrollBehavior
        })
      }
    }, 50)
  }

  // 设置 ResizeObserver
  function setupResizeObserver(onResize?: () => void): void {
    if (!containerRef.value) return

    resizeObserver = new ResizeObserver(() => {
      if (!isResizing.value) {
        isResizing.value = true
      }

      if (resizeTimeout) {
        clearTimeout(resizeTimeout)
      }

      resizeTimeout = setTimeout(() => {
        if (isResizing.value) {
          if (onResize) {
            onResize()
          }
          isResizing.value = false
        }
      }, 150)
    })

    resizeObserver.observe(containerRef.value)
  }

  // 清理 ResizeObserver
  function cleanupResizeObserver(): void {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    if (resizeTimeout) {
      clearTimeout(resizeTimeout)
      resizeTimeout = null
    }
  }

  // 更新最后用户触发的页面
  function setLastUserTriggeredPage(page: number): void {
    lastUserTriggeredPage.value = page
  }

  return {
    isPointerOverPdf,
    linksDisabled,
    isResizing,
    mouseDownInfo,
    lastUserTriggeredPage: readonly(lastUserTriggeredPage),
    handleMouseEnterContainer,
    handleMouseLeaveContainer,
    handleScroll,
    handleWheel,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    scrollToPage,
    setupResizeObserver,
    cleanupResizeObserver,
    setLastUserTriggeredPage
  }
}

export type InteractionsManager = ReturnType<typeof useInteractions>
