/**
 * 文本选择和高亮 Composable
 * 处理文本选择、高亮点击、工具提示等
 */

import { ref } from 'vue'
import type { Position } from '../types/pdf'
import type { Highlight } from '../../../stores/pdf'
import { IoU, findPageElement } from '../utils/pdfHelpers'

export interface SelectionInfo {
  page: number
  rects: Array<{
    left: number
    top: number
    width: number
    height: number
  }>
}

export interface TextSelectionOptions {
  onSelectText?: (text: string, position: Position, selectionInfo: SelectionInfo) => void
  onSelectHighlight?: (highlight: Highlight, position: Position) => void
  onClearSelection?: () => void
  getHighlightsAtPoint?: (page: number, x: number, y: number) => Highlight[]
}

export function useTextSelection(options: TextSelectionOptions = {}) {
  // 状态
  const showTooltip = ref(false)
  const tooltipPosition = ref<Position>({ x: 0, y: 0 })
  const highlightsAtCurrentPoint = ref<Highlight[]>([])
  const currentHighlightIndex = ref(0)

  // 手动文本选择处理
  function handleTextSelection(): void {
    const selection = window.getSelection()

    if (!selection || !selection.toString().trim()) {
      return
    }

    if (options.onClearSelection) {
      options.onClearSelection()
    }

    const text = selection.toString().trim()
    const range = selection.getRangeAt(0)
    const pageEl = findPageElement(range.commonAncestorContainer)

    if (!pageEl || !pageEl.dataset.page) {
      return
    }

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
        height: rect.height / layerRect.height,
      }))
      .filter((rect) => rect.width > 0 && rect.height > 0)

    if (!rects.length) return

    // IoU 去重
    const dedupedRects: typeof rects = []
    rects.forEach((rect) => {
      const isDuplicate = dedupedRects.some((existing) => IoU(rect, existing) > 0.3)
      if (!isDuplicate) {
        dedupedRects.push(rect)
      }
    })

    const selectionRect = range.getBoundingClientRect()
    const position: Position = {
      x: selectionRect.left + selectionRect.width / 2,
      y: selectionRect.top - 10
    }

    tooltipPosition.value = position
    showTooltip.value = true

    if (options.onSelectText) {
      options.onSelectText(text, position, { page: pageNumber, rects: dedupedRects })
    }
  }

  // 处理点击事件（高亮选择）
  function handleHighlightClick(event: MouseEvent): void {
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

    let highlightsAtPoint: Highlight[] = []
    if (options.getHighlightsAtPoint) {
      highlightsAtPoint = options.getHighlightsAtPoint(pageNumber, normalizedX, normalizedY)
    }

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

    tooltipPosition.value = { x: tooltipX, y: tooltipY }
    showTooltip.value = true

    if (options.onSelectHighlight) {
      options.onSelectHighlight(selectedHighlight, { x: tooltipX, y: tooltipY })
    }

    window.getSelection()?.removeAllRanges()
  }

  // 点击外部处理
  function handleClickOutside(forceClose: boolean = false): void {
    const selection = window.getSelection()
    if (!forceClose && selection && selection.toString().trim()) return

    selection?.removeAllRanges()

    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0

    if (options.onClearSelection) {
      options.onClearSelection()
    }
  }

  // 关闭工具提示
  function closeTooltip(): void {
    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0

    if (options.onClearSelection) {
      options.onClearSelection()
    }
  }

  return {
    showTooltip,
    tooltipPosition,
    highlightsAtCurrentPoint,
    currentHighlightIndex,
    handleTextSelection,
    handleHighlightClick,
    handleClickOutside,
    closeTooltip
  }
}

export type TextSelectionManager = ReturnType<typeof useTextSelection>
