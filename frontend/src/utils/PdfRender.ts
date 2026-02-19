/**
 * PDF 渲染相关工具函数
 * 处理 Link Layer、Text Layer 的渲染
 */

import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { LinkOverlayRect, PageRef } from '../types/pdf'
import { 
  appendInternalLinkOverlay, 
  resolveDestination, 
  type DestinationCoords 
} from './InternalLink'

export { 
  fetchInternalLinkData, 
  appendInternalLinkOverlay, 
  getParagraphByCoords, 
  resolveDestination, 
  type DestinationCoords, 
  type InternalLinkResult 
} from './InternalLink'

/**
 * 添加外部链接覆盖层
 */
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

/**
 * 渲染 Link Layer
 */
export async function renderLinkLayer(
  annotations: unknown[],
  viewport: { convertToViewportRectangle: (rect: number[]) => number[] },
  container: HTMLElement,
  pdfDoc: PDFDocumentProxy,
  onInternalLinkClick: (dest: DestinationCoords, clickX: number, clickY: number) => void,
  onDirectJump?: (dest: DestinationCoords) => void
): Promise<void> {
  container.innerHTML = ''

  for (const annotation of annotations) {
    const annot = annotation as {
      subtype: string
      rect: number[]
      url?: string
      dest?: unknown
      action?: { dest?: unknown }
    }

    if (annot.subtype !== 'Link') continue

    // 计算注释在视口中的位置
    const rect = viewport.convertToViewportRectangle(annot.rect) as number[]
    if (rect.length < 4) continue
    const [x1, y1, x2, y2] = rect
    const overlayRect: LinkOverlayRect = {
      left: Math.min(x1!, x2!),
      top: Math.min(y1!, y2!),
      width: Math.abs(x2! - x1!),
      height: Math.abs(y2! - y1!)
    }

    if (annot.url) {
      // 外部链接
      appendLinkOverlay(container, overlayRect, annot.url, annot.url || 'External Link')
    } else if (annot.dest) {
      // 内部链接（如论文引用）- 延迟解析目标坐标到点击时
      appendInternalLinkOverlay(
        container,
        overlayRect,
        annot.dest,
        pdfDoc,
        onInternalLinkClick,
        onDirectJump,
        '点击跳转到引用位置'
      )
    } else if (annot.action?.dest) {
      // 带 action 的内部链接 - 延迟解析目标坐标到点击时
      appendInternalLinkOverlay(
        container,
        overlayRect,
        annot.action.dest,
        pdfDoc,
        onInternalLinkClick,
        onDirectJump,
        '点击跳转到引用位置'
      )
    }
  }
}

/**
 * 修复 Text Layer 文字宽度对齐
 */
export function fixTextLayerWidth(
  textContent: { items: unknown[] },
  textDivs: HTMLElement[],
  cssViewport: { scale: number }
): void {
  if (!textContent?.items || textDivs.length !== textContent.items.length) return

  const items = textContent.items as Array<{
    str?: string
    width?: number
    transform?: number[]
  }>

  for (let i = 0; i < items.length; i++) {
    const item = items[i]!
    const div = textDivs[i]

    if (!item?.str || !item?.width || !div) continue

    const targetWidth = item.width * cssViewport.scale
    const rect = div.getBoundingClientRect()

    const transform = item.transform
    const isVertical = transform ? Math.abs(transform[0]!) < 1e-3 && Math.abs(transform[3]!) < 1e-3 : false
    const isHorizontal = !transform || (Math.abs(transform[1]!) < 1e-3 && Math.abs(transform[2]!) < 1e-3)

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

/**
 * 应用过渡缩放效果
 */
export function applyInterimScaleToPage(
  refs: PageRef,
  _pageNumber: number,
  targetScale: number,
  lastRenderedScale: number | undefined,
  pageSize: { width: number; height: number }
): void {
  const renderedScale = lastRenderedScale ?? targetScale
  const ratio = renderedScale ? targetScale / renderedScale : 1

  const baseWidth = Math.floor(pageSize.width * renderedScale)
  const baseHeight = Math.floor(pageSize.height * renderedScale)
  const targetWidth = Math.floor(pageSize.width * targetScale)
  const targetHeight = Math.floor(pageSize.height * targetScale)

  // Canvas 直接用目标尺寸拉伸
  refs.canvas.style.width = `${targetWidth}px`
  refs.canvas.style.height = `${targetHeight}px`

  // 文本层保持"旧尺度"尺寸，通过 transform 过渡
  refs.textLayer.style.width = `${baseWidth}px`
  refs.textLayer.style.height = `${baseHeight}px`
  refs.textLayer.style.transformOrigin = 'top left'
  refs.textLayer.style.transform = `scale(${ratio})`

  // 链接层同样按旧尺寸 + 缩放
  refs.linkLayer.style.width = `${baseWidth}px`
  refs.linkLayer.style.height = `${baseHeight}px`
  refs.linkLayer.style.transformOrigin = 'top left'
  refs.linkLayer.style.transform = `scale(${ratio})`

  // 高亮层同步缩放
  refs.highlightLayer.style.width = `${baseWidth}px`
  refs.highlightLayer.style.height = `${baseHeight}px`
  refs.highlightLayer.style.transformOrigin = 'top left'
  refs.highlightLayer.style.transform = `scale(${ratio})`
}
