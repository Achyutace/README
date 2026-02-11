/**
 * PDF 文本选择和高亮 Composable
 * 处理文本选择、高亮点击、Tooltip 显示
 */

import { ref } from 'vue'
import { findPageElement, calculateIoU, CLICK_TIME_THRESHOLD, DRAG_DISTANCE_THRESHOLD } from '../utils/PdfHelper'
import type { HighlightItem } from '../types/pdf'

export interface SelectionPosition {
  x: number
  y: number
}

export interface UsePdfSelectionOptions {
  onTextSelected?: (text: string, position: SelectionPosition, pageNumber: number, rects: Array<{ left: number; top: number; width: number; height: number }>) => void
  onHighlightSelected?: (highlight: HighlightItem, position: SelectionPosition) => void
  onClickOutside?: (forceClose: boolean) => void
  getHighlightsAtPoint?: (pageNumber: number, x: number, y: number) => HighlightItem[]
  getHighlightsByPage?: (pageNumber: number) => HighlightItem[]
}

export function usePdfSelection(options: UsePdfSelectionOptions = {}) {
  const showTooltip = ref(false)
  const tooltipPosition = ref<SelectionPosition>({ x: 0, y: 0 })
  
  // 循环选择高亮相关
  const highlightsAtCurrentPoint = ref<HighlightItem[]>([])
  const currentHighlightIndex = ref(0)

  // 点击/拖动检测相关
  const mouseDownInfo = ref<{ x: number; y: number; time: number } | null>(null)
  const linksDisabled = ref(false)

  /**
   * 处理鼠标按下
   */
  function handleMouseDown(event: MouseEvent): void {
    mouseDownInfo.value = {
      x: event.clientX,
      y: event.clientY,
      time: Date.now()
    }
    linksDisabled.value = false
  }

  /**
   * 处理鼠标移动
   */
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

  /**
   * 处理鼠标抬起
   */
  function handleMouseUp(event: MouseEvent): boolean {
    const downInfo = mouseDownInfo.value
    mouseDownInfo.value = null

    const isDrag = !!downInfo && (
      (Date.now() - downInfo.time >= CLICK_TIME_THRESHOLD) ||
      (Math.hypot(event.clientX - downInfo.x, event.clientY - downInfo.y) >= DRAG_DISTANCE_THRESHOLD)
    )

    if (isDrag) {
      handleTextSelection()
      linksDisabled.value = false
      return false // 表示是拖动
    }

    // 检查是否点击在链接上
    const target = event.target as HTMLElement
    if (target.tagName === 'A' || target.closest('a') || target.classList.contains('internal-link') || target.closest('.internal-link')) {
      linksDisabled.value = false
      return false // 点击在链接上
    }

    return true // 是普通点击
  }

  /**
   * 处理普通点击
   */
  function handleClick(event: MouseEvent): void {
    const pageEl = findPageElement(event.target as Node)
    if (!pageEl || !pageEl.dataset.page) {
      options.onClickOutside?.(true)
      return
    }

    const pageNumber = Number(pageEl.dataset.page)
    const textLayer = pageEl.querySelector('.textLayer') as HTMLDivElement | null
    if (!textLayer) return

    const layerRect = textLayer.getBoundingClientRect()
    if (!layerRect.width || !layerRect.height) return

    const normalizedX = (event.clientX - layerRect.left) / layerRect.width
    const normalizedY = (event.clientY - layerRect.top) / layerRect.height

    const highlightsAtPoint = options.getHighlightsAtPoint?.(pageNumber, normalizedX, normalizedY) || []

    if (highlightsAtPoint.length === 0) {
      options.onClickOutside?.(true)
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

    tooltipPosition.value = { x: tooltipX, y: tooltipY }
    showTooltip.value = true

    options.onHighlightSelected?.(selectedHighlight, { x: tooltipX, y: tooltipY })

    window.getSelection()?.removeAllRanges()
  }

  /**
   * 处理文本选择
   */
  function handleTextSelection(): void {
    const selection = window.getSelection()
    if (!selection || !selection.toString().trim()) return

    const text = selection.toString().trim()
    const range = selection.getRangeAt(0)
    const pageEl = findPageElement(range.commonAncestorContainer)

    if (!pageEl || !pageEl.dataset.page) return

    const pageNumber = Number(pageEl.dataset.page)
    const textLayer = pageEl.querySelector('.textLayer') as HTMLDivElement | null
    if (!textLayer) return

    const layerRect = textLayer.getBoundingClientRect()
    if (!layerRect.width || !layerRect.height) return

    const rects = Array.from(range.getClientRects())
      .map((rect) => ({
        left: (rect.left - layerRect.left) / layerRect.width,
        top: (rect.top - layerRect.top) / layerRect.height,
        width: rect.width / layerRect.width,
        height: rect.height / layerRect.height
      }))
      .filter((rect) => rect.width > 0 && rect.height > 0)

    if (!rects.length) return

    // IoU 去重
    const dedupedRects = rects.filter((rect, index) => {
      const previousRects = rects.slice(0, index)
      return !previousRects.some(existing => calculateIoU(rect, existing) > 0.3)
    })

    const selectionRect = range.getBoundingClientRect()
    const position = {
      x: selectionRect.left + selectionRect.width / 2,
      y: selectionRect.top - 10
    }

    tooltipPosition.value = position
    showTooltip.value = true

    options.onTextSelected?.(text, position, pageNumber, dedupedRects)
  }

  /**
   * 关闭 Tooltip
   */
  function closeTooltip(): void {
    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0
    window.getSelection()?.removeAllRanges()
  }

  return {
    showTooltip,
    tooltipPosition,
    highlightsAtCurrentPoint,
    currentHighlightIndex,
    linksDisabled,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleClick,
    handleTextSelection,
    closeTooltip
  }
}
