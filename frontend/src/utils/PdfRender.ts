/**
 * PDF 渲染相关工具函数
 * 处理 Link Layer、Text Layer 的渲染
 */

import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { LinkOverlayRect, PageRef } from '../types/pdf'
import type { PdfParagraph } from '../types'

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
 * 检查目标是否为直接跳转类型
 * 以 "cite:" 开头的按论文引用处理（弹窗），其他一律直接跳转
 */
function isDirectJumpDestination(dest: unknown): boolean {
  if (typeof dest === 'string') {
    const lowerDest = dest.toLowerCase()
    // 以 cite: 开头的按论文处理（不直接跳转）
    return !lowerDest.startsWith('cite.')
  }
  // 非字符串类型的目标也直接跳转
  return true
}

/**
 * 添加内部链接覆盖层
 * 点击时才解析目标坐标（延迟解析以优化性能）
 * 对于 table, section, figure, appendix 开头的链接直接跳转
 */
export function appendInternalLinkOverlay(
  container: HTMLElement,
  rect: LinkOverlayRect,
  rawDest: unknown,
  pdfDoc: PDFDocumentProxy,
  onClick: (destCoords: DestinationCoords, clickX: number, clickY: number) => void,
  onDirectJump?: (destCoords: DestinationCoords) => void,
  title?: string
): void {
  const link = document.createElement('div')
  link.title = title || '内部链接'
  link.style.display = 'block'
  link.style.left = `${rect.left}px`
  link.style.top = `${rect.top}px`
  link.style.width = `${rect.width}px`
  link.style.height = `${rect.height}px`
  link.style.position = 'absolute'
  link.className = 'hover:bg-blue-200/30 cursor-pointer internal-link'

  // 判断是否为直接跳转类型
  const isDirectJump = isDirectJumpDestination(rawDest)

  // 防止与容器的点击处理冲突
  link.addEventListener('mousedown', (e) => {
    e.stopPropagation()
  })

  link.addEventListener('click', async (e) => {
    e.preventDefault()
    e.stopPropagation()
    // 点击时才解析目标坐标
    const destCoords = await resolveDestination(pdfDoc, rawDest)
    if (destCoords) {
      if (isDirectJump && onDirectJump) {
        // 直接跳转到目标位置
        onDirectJump(destCoords)
      } else {
        // 显示弹窗
        onClick(destCoords, e.clientX, e.clientY)
      }
    }
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
 * 根据页码和坐标获取对应的自然段
 * 注意：传入的坐标是 PDF 坐标系（原点在左下角，Y 轴向上）
 * 但 paragraph.bbox 存储的是 CSS 坐标系（原点在左上角，Y 轴向下）
 * @param page - 页码（1-based）
 * @param x - X 坐标（PDF 用户空间单位，从左向右）
 * @param y - Y 坐标（PDF 用户空间单位，从下向上）
 * @param paragraphs - 段落数组
 * @param pageHeight - 页面高度（PDF 单位），用于坐标转换，必须提供
 * @returns 匹配的 PdfParagraph 或 null
 */
export function getParagraphByCoords(
  page: number,
  x: number | null,
  y: number | null,
  paragraphs: PdfParagraph[],
): PdfParagraph | null {
  if (!paragraphs || paragraphs.length === 0) return null
  if (x === null || y === null) return null

  // 筛选出目标页面的段落
  const pageParagraphs = paragraphs.filter(p => p.page === page)
  if (pageParagraphs.length === 0) return null

  // 找到包含该坐标的段落
  // bbox 格式: { x0, y0, x1, y1, width, height }
  // 在前端存储的 bbox 中，y0 和 y1 是 CSS 坐标系（原点在左上角，y 向下增长）
  // paragraphs 已按 y0 排序，利用相邻段落 y0 的中点来确定归属范围
  const n = pageParagraphs.length
  if (n === 1) {
    return pageParagraphs[0]!
  }

  for (let i = 0; i < n; i++) {
    const paragraph = pageParagraphs[i]!
    const y0 = paragraph.bbox.y0

    if (i === 0) {
      // 第一个段落：y < (y0[0] + y0[1]) / 2
      const mid = (y0 + pageParagraphs[1]!.bbox.y0) / 2
      if (y < mid) {
        return paragraph
      }
    } else if (i === n - 1) {
      // 最后一个段落：y >= (y0[n-2] + y0[n-1]) / 2
      return paragraph
    } else {
      // 中间段落：(y0[i-1] + y0[i]) / 2 <= y < (y0[i] + y0[i+1]) / 2
      const prevMid = (pageParagraphs[i - 1]!.bbox.y0 + y0) / 2
      const nextMid = (y0 + pageParagraphs[i + 1]!.bbox.y0) / 2
      if (y >= prevMid && y < nextMid) {
        return paragraph
      }
    }
  }

  return null
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
    console.log('Resolving destination:', dest)

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
    const pageNumber = pageIndex + 1 // 页码从 1 开始

    // 获取页面尺寸（直接从 PDF 文档获取，不依赖 store）
    const page = await pdfDoc.getPage(pageNumber)
    const viewport = page.getViewport({ scale: 1 })
    const pageHeight = viewport.height

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
      page: pageNumber,
      x,
      y: pageHeight - (y ?? 0),
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
