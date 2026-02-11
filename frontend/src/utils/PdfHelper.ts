/**
 * PDF 查看器工具函数
 * 纯函数，不依赖 Vue 响应式系统
 */

import type { PageSize, HighlightRect } from '../types/pdf'

/** 页面间距（像素） */
export const PAGE_GAP = 16 // space-y-4 = 16px

/** 容器内边距（像素） */
export const CONTAINER_PADDING = 16 // p-4 = 16px

/** 点击时间阈值（毫秒）- 小于此值视为点击 */
export const CLICK_TIME_THRESHOLD = 300

/** 拖动距离阈值（像素）- 超过此值视为拖动 */
export const DRAG_DISTANCE_THRESHOLD = 6

/**
 * 获取指定页面的原始尺寸
 */
export function getPageSize(
  pageNumber: number,
  pageSizesConstant: PageSize | null,
  pageSizesArray: PageSize[] | null
): PageSize {
  if (pageSizesConstant) {
    return pageSizesConstant
  }
  if (pageSizesArray) {
    return pageSizesArray[pageNumber - 1] ?? { width: 612, height: 792 }
  }
  // 默认 A4 尺寸
  return { width: 612, height: 792 }
}

/**
 * 获取指定页面的缩放后尺寸
 */
export function getScaledPageSize(
  pageNumber: number,
  scale: number,
  pageSizesConstant: PageSize | null,
  pageSizesArray: PageSize[] | null
): PageSize {
  const size = getPageSize(pageNumber, pageSizesConstant, pageSizesArray) || { width: 612, height: 792 }
  return {
    width: Math.floor(size.width * scale),
    height: Math.floor(size.height * scale)
  }
}

/**
 * 获取页面顶部距离容器顶部的距离（像素）
 */
export function getPageTop(
  pageNumber: number,
  scale: number,
  pageSizesConstant: PageSize | null,
  pageHeightAccumulator: number[]
): number {
  const index = pageNumber - 1
  if (index < 0) return CONTAINER_PADDING

  // 常数高度情况 - O(1)
  if (pageSizesConstant) {
    const h = pageSizesConstant.height * scale
    return Math.round(CONTAINER_PADDING + index * (h + PAGE_GAP))
  }

  // 变长高度情况 - O(1) 查表
  if (pageHeightAccumulator.length > index) {
    const accH = pageHeightAccumulator[index] ?? 0
    return Math.round(CONTAINER_PADDING + accH * scale + index * PAGE_GAP)
  }

  return CONTAINER_PADDING
}

/**
 * 根据垂直滚动位置查找页码
 */
export function getPageAtY(
  y: number,
  totalPages: number,
  scale: number,
  pageSizesConstant: PageSize | null,
  pageHeightAccumulator: number[]
): number {
  if (totalPages === 0) return 1

  const yAdjusted = y - CONTAINER_PADDING
  if (yAdjusted < 0) return 1

  // 常数PDF高度情况 - 直接计算 O(1)
  if (pageSizesConstant) {
    const itemHeight = pageSizesConstant.height * scale + PAGE_GAP
    const index = Math.floor(yAdjusted / itemHeight)
    return Math.max(1, Math.min(totalPages, index + 1))
  }

  // 变长PDF高度情况 - 二分查找 O(log N)
  let low = 1, high = totalPages
  let result = 1
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    const top = getPageTop(mid, scale, pageSizesConstant, pageHeightAccumulator)

    if (y >= top) {
      result = mid
      low = mid + 1
    } else {
      high = mid - 1
    }
  }
  return result
}

/**
 * 查找页面元素（向上遍历 DOM 树）
 */
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

/**
 * 将十六进制颜色转换为 RGBA
 */
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

/**
 * 获取高亮颜色（带透明度）
 */
export function getHighlightColor(color: string): string {
  return hexToRgba(color, 0.35)
}

/**
 * 计算边界框样式
 */
export function getBoundingBoxStyle(rects: HighlightRect[]): Record<string, string> {
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

/**
 * 计算两个矩形的 IoU（交并比）
 */
export function calculateIoU(
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

  if (boxAArea + boxBArea - intersectionArea === 0) return 0
  return intersectionArea / (boxAArea + boxBArea - intersectionArea)
}

/**
 * 计算段落光标位置样式
 */
export function getParagraphMarkerStyle(
  paragraph: { bbox: { x0: number; y0: number } },
  pageSize: PageSize | null
): Record<string, string> {
  if (!pageSize) return { display: 'none' }

  const left = (paragraph.bbox.x0 / pageSize.width) * 100
  const top = (paragraph.bbox.y0 / pageSize.height) * 100

  return {
    left: `${left}%`,
    top: `${top}%`,
    transform: 'translate(-100%, -50%)'
  }
}
