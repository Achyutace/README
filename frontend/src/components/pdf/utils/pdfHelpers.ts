/**
 * PDF 辅助函数
 */

import type { LinkOverlayRect } from '../types/pdf'

// 常量定义
export const PAGE_GAP = 16 // space-y-4 = 16px
export const CONTAINER_PADDING = 16 // p-4 = 16px
export const CLICK_TIME_THRESHOLD = 300 // 点击时间小于此值视为点击（毫秒）
export const DRAG_DISTANCE_THRESHOLD = 6 // 鼠标移动超过此像素数视为拖动（px）

// 颜色转换：十六进制转 RGBA
export function hexToRgba(color: string, alpha = 0.35): string {
  const hex = color.replace('#', '')
  const fallback = `rgba(246, 224, 94, ${alpha})`

  if (hex.length !== 3 && hex.length !== 6) return fallback

  const normalized = hex.length === 3
    ? hex.split('').map(ch => ch + ch).join('')
    : hex

  const intVal = Number.parseInt(normalized, 16)
  if (Number.isNaN(intVal)) return fallback

  const r = (intVal >> 16) & 255
  const g = (intVal >> 8) & 255
  const b = intVal & 255

  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// 获取高亮颜色
export function getHighlightColor(color: string): string {
  return hexToRgba(color, 0.35)
}

// 计算 IoU（交并比）
export function IoU(
  rectA: { left: number; top: number; width: number; height: number },
  rectB: { left: number; top: number; width: number; height: number }
): number {
  const xA = Math.max(rectA.left, rectB.left)
  const yA = Math.max(rectA.top, rectB.top)
  const xB = Math.min(rectA.left + rectA.width, rectB.left + rectB.width)
  const yB = Math.min(rectA.top + rectA.height, rectB.top + rectB.height)

  const intersectionArea = Math.max(0, xB - xA) * Math.max(0, yB - yA)
  const boxAArea = rectA.width * rectA.height
  const boxBArea = rectB.width * rectB.height

  const iou = intersectionArea / (boxAArea + boxBArea - intersectionArea)
  return iou
}

// 获取边界框样式
export function getBoundingBoxStyle(
  rects: { left: number; top: number; width: number; height: number }[]
): Record<string, string> {
  if (!rects || rects.length === 0) return {}

  let minLeft = Infinity
  let minTop = Infinity
  let maxRight = -Infinity
  let maxBottom = -Infinity

  rects.forEach(rect => {
    minLeft = Math.min(minLeft, rect.left)
    minTop = Math.min(minTop, rect.top)
    maxRight = Math.max(maxRight, rect.left + rect.width)
    maxBottom = Math.max(maxBottom, rect.top + rect.height)
  })

  return {
    left: `${minLeft * 100}%`,
    top: `${minTop * 100}%`,
    width: `${(maxRight - minLeft) * 100}%`,
    height: `${(maxBottom - minTop) * 100}%`
  }
}

// 查找页面元素
export function findPageElement(node: Node | null): HTMLElement | null {
  let current: Node | null = node
  while (current) {
    if (current instanceof HTMLElement && current.classList.contains('pdf-page')) {
      return current
    }
    current = current.parentElement || current.parentNode
  }
  return null
}

// 外部链接的 HTML 格式
export function appendLinkOverlay(
  container: HTMLElement,
  rect: LinkOverlayRect,
  href: string,
  title?: string
): void {
  const link = document.createElement('a')
  // 最终设置前移除 URL 内部空格，避免不可点击
  link.href = href.replace(/[\s\u00A0\u200B-\u200D\uFEFF]+/g, '')
  link.target = '_blank'
  link.rel = 'noreferrer noopener'
  link.title = title || href
  link.style.display = 'block'
  link.style.left = `${rect.left}px`
  link.style.top = `${rect.top}px`
  link.style.width = `${rect.width}px`
  link.style.height = `${rect.height}px`
  link.style.position = 'absolute'
  link.className = 'hover:bg-yellow-200/20 cursor-pointer'
  container.appendChild(link)
}

// 内部链接的 HTML 格式
export function appendInternalLinkOverlay(
  container: HTMLElement,
  rect: LinkOverlayRect,
  destPage: number,
  title?: string,
  onClick?: (page: number) => void
): void {
  const link = document.createElement('div')
  link.dataset.destPage = String(destPage)
  link.title = title || `跳转到第 ${destPage} 页`
  link.style.display = 'block'
  link.style.left = `${rect.left}px`
  link.style.top = `${rect.top}px`
  link.style.width = `${rect.width}px`
  link.style.height = `${rect.height}px`
  link.style.position = 'absolute'
  link.className = 'hover:bg-blue-200/30 cursor-pointer internal-link'

  // 防止与容器的点击处理冲突
  link.addEventListener('mousedown', (e) => {
    e.stopPropagation()
  })

  link.addEventListener('click', (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (onClick) {
      onClick(destPage)
    }
  })
  container.appendChild(link)
}

// 获取点击位置的单词
export function getWordAtPoint(x: number, y: number): string | null {
  let range: Range | null = null

  // 获取点击位置 (Chrome, Edge, Safari 版本)
  if (typeof (document as any).caretRangeFromPoint === 'function') {
    range = (document as any).caretRangeFromPoint(x, y)
  }
  // 获取点击位置 (Firefox 版本)
  else if (typeof (document as any).caretPositionFromPoint === 'function') {
    const pos = (document as any).caretPositionFromPoint(x, y)
    if (pos && pos.offsetNode) {
      const newRange = document.createRange()
      newRange.setStart(pos.offsetNode, pos.offset)
      newRange.setEnd(pos.offsetNode, pos.offset)
      range = newRange
    }
  }

  if (!range) return null

  const node = range.startContainer
  if (node.nodeType !== Node.TEXT_NODE) return null

  const text = node.textContent || ''
  const offset = range.startOffset

  // 查找单词边界
  let start = offset
  let end = offset

  // 向前找单词开始
  while (start > 0 && /[\w\u4e00-\u9fa5]/.test(text[start - 1] || '')) {
    start--
  }

  // 向后找单词结束
  while (end < text.length && /[\w\u4e00-\u9fa5]/.test(text[end] || '')) {
    end++
  }

  if (start === end) return null

  return text.slice(start, end).trim()
}
