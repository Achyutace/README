/**
 * PDF 渲染相关工具函数
 * 处理 Link Layer、Text Layer 的渲染
 */

import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { LinkOverlayRect, PageRef } from '../types/pdf'

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
 * 添加内部链接覆盖层
 */
export function appendInternalLinkOverlay(
  container: HTMLElement,
  rect: LinkOverlayRect,
  destCoords: DestinationCoords,
  onClick: (dest: DestinationCoords, clickX: number, clickY: number) => void,
  title?: string
): void {
  const link = document.createElement('div')
  link.dataset.destPage = String(destCoords.page)
  link.title = title || `跳转到第 ${destCoords.page} 页`
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
    onClick(destCoords, e.clientX, e.clientY)
  })
  container.appendChild(link)
}

/**
 * PDF 内部链接目标坐标
 * XYZ 目标类型: [pageRef, 'XYZ', x, y, zoom]
 * Fit 目标类型: [pageRef, 'Fit']
 * FitH 目标类型: [pageRef, 'FitH', top]
 */
export type DestinationCoords = {
  /** 目标页码 */
  page: number
  /** X 坐标 (PDF 用户空间单位) */
  x: number | null
  /** Y 坐标 (PDF 用户空间单位) */
  y: number | null
  /** 缩放级别 (null 表示保持当前缩放) */
  zoom: number | null
  /** 目标类型: XYZ, Fit, FitH, FitV, FitR, FitB, FitBH, FitBV */
  type: string
}

/**
 * 解析 PDF 内部链接目标页码和坐标
 */
export async function resolveDestination(
  pdfDoc: PDFDocumentProxy,
  dest: unknown
): Promise<DestinationCoords | null> {
  if (!pdfDoc) return null

  try {
    let destArray = dest

    // 如果目标是 String，需要先解析
    if (typeof dest === 'string') {
      destArray = await pdfDoc.getDestination(dest)
    }

    // 确保目标是数组
    if (!destArray || !Array.isArray(destArray)) return null

    // 目标数组的第一个元素是页面引用
    const pageRef = destArray[0]
    if (!pageRef) return null

    // 获取页码
    const pageIndex = await pdfDoc.getPageIndex(pageRef)

    // 解析目标类型和坐标
    // destArray[1] 可能是字符串或 {name: string} 对象
    const destTypeRaw = destArray[1]
    const destType = typeof destTypeRaw === 'string' 
      ? destTypeRaw 
      : (destTypeRaw as { name?: string })?.name || 'Fit'
    
    let x: number | null = null
    let y: number | null = null
    let zoom: number | null = null

    switch (destType) {
      case 'XYZ':
        // [pageRef, 'XYZ', x, y, zoom]
        x = typeof destArray[2] === 'number' ? destArray[2] : null
        y = typeof destArray[3] === 'number' ? destArray[3] : null
        zoom = typeof destArray[4] === 'number' ? destArray[4] : null
        break
      case 'FitH':
      case 'FitBH':
        // [pageRef, 'FitH', top]
        y = typeof destArray[2] === 'number' ? destArray[2] : null
        break
      case 'FitV':
      case 'FitBV':
        // [pageRef, 'FitV', left]
        x = typeof destArray[2] === 'number' ? destArray[2] : null
        break
      case 'FitR':
        // [pageRef, 'FitR', left, bottom, right, top]
        x = typeof destArray[2] === 'number' ? destArray[2] : null
        y = typeof destArray[5] === 'number' ? destArray[5] : null
        break
      case 'Fit':
      case 'FitB':
      default:
        // 无特定坐标，适应页面
        console.warn(`Unsupported destination type "${destType}", defaulting to "Fit"`)
        break
    }

    return {
      page: pageIndex + 1, // 页码从 1 开始
      x,
      y,
      zoom,
      type: destType || 'Fit'
    }

  } catch (err) {
    console.error('Error resolving destination:', err)
    return null
  }
}

/**
 * 渲染 Link Layer
 */
export async function renderLinkLayer(
  annotations: unknown[],
  viewport: { convertToViewportRectangle: (rect: number[]) => number[] },
  container: HTMLElement,
  pdfDoc: PDFDocumentProxy,
  onInternalLinkClick: (dest: DestinationCoords, clickX: number, clickY: number) => void
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
      // 内部链接（如论文引用）
      const destCoords = await resolveDestination(pdfDoc, annot.dest)
      if (destCoords) {
        appendInternalLinkOverlay(
          container,
          overlayRect,
          destCoords,
          onInternalLinkClick,
          `跳转到第 ${destCoords.page} 页`
        )
      }
    } else if (annot.action?.dest) {
      // 带 action 的内部链接
      const destCoords = await resolveDestination(pdfDoc, annot.action.dest)
      if (destCoords) {
        appendInternalLinkOverlay(
          container,
          overlayRect,
          destCoords,
          onInternalLinkClick,
          `跳转到第 ${destCoords.page} 页`
        )
      }
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
