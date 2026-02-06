/**
 * PDF 查看器类型定义
 */

import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist'

// 每一页的元素定义
// 包含 页面容器、Canvas 层、Text 层和 Link 层
export type PageRef = {
  container: HTMLElement // 页面容器元素引用
  canvas: HTMLCanvasElement // 页面绘制的画布引用
  textLayer: HTMLDivElement // 文字图层容器引用
  linkLayer: HTMLDivElement // 链接图层容器引用
  highlightLayer: HTMLDivElement // 高亮图层容器引用
}

// 缩放锚点：包含页码、垂直/水平比例、以及目标回复的屏幕坐标（可选）
export type ZoomAnchor = {
  page: number
  ratioY: number
  ratioX: number
  destX?: number // 鼠标缩放时的目标屏幕X
  destY?: number // 鼠标缩放时的目标屏幕Y
}

// Link Layer 定义
export type LinkOverlayRect = {
  left: number
  top: number
  width: number
  height: number
}

// 页面尺寸
export type PageSize = {
  width: number
  height: number
}

// 鼠标按下信息
export type MouseDownInfo = {
  x: number
  y: number
  time: number
}

// 坐标位置
export type Position = {
  x: number
  y: number
}

// PDF 渲染相关状态
export interface PdfRenderState {
  pdfDoc: PDFDocumentProxy | null
  pageRefs: Map<number, PageRef>
  renderTasks: Map<number, RenderTask>
  renderedPages: Set<number>
  pagesNeedingRefresh: Set<number>
  lastRenderedScale: Map<number, number>
}
