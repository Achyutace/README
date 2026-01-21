<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, shallowRef, watch, type ComponentPublicInstance } from 'vue' // 引入 Vue 核心 API 与组件实例类型
import { useDebounceFn } from '@vueuse/core' // 引入防抖工具
import {
  getDocument,
  GlobalWorkerOptions,
  renderTextLayer,
  type PDFDocumentProxy,
  type RenderTask,
} from 'pdfjs-dist' // 引入 pdf.js 的核心加载与渲染工具
import 'pdfjs-dist/web/pdf_viewer.css' // 引入 pdf.js 默认样式以展示文字图层

// Use the ESM worker build so Vite can bundle it correctly
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.js?url' // 使用 ?url 显式引入 worker
import { usePdfStore } from '../../stores/pdf' // 使用 Pinia 中的 PDF 状态仓库
import { useLibraryStore } from '../../stores/library' // 使用 Pinia 中的文库状态仓库
import TextSelectionTooltip from './TextSelectionTooltip.vue' // 导入文字选中提示组件

GlobalWorkerOptions.workerSrc = pdfWorker // 设置 pdf.js 全局 worker 路径

type PageRef = {
  container: HTMLElement // 页面容器元素引用
  canvas: HTMLCanvasElement // 页面绘制的画布引用
  textLayer: HTMLDivElement // 文字图层容器引用
  linkLayer: HTMLDivElement // 链接图层容器引用
}

const pdfStore = usePdfStore() // 获取 PDF 仓库实例
const libraryStore = useLibraryStore() // 获取文库仓库实例

const containerRef = ref<HTMLElement | null>(null) // 根滚动容器引用
const pdfDoc = shallowRef<PDFDocumentProxy | null>(null) // 当前加载的 PDF 文档实例
const pageNumbers = ref<number[]>([]) // 页面序号集合
const pageRefs = new Map<number, PageRef>() // 每页元素引用集合
const renderTasks = new Map<number, RenderTask>() // 每页渲染任务集合
const visiblePages = new Set<number>() // 当前可见页面集合

const showTooltip = ref(false) // 是否显示选中文本的工具提示
const tooltipPosition = ref({ x: 0, y: 0 }) // 工具提示的坐标
const isProgrammaticScrolling = ref(false) // 标记是否正在进行程序化滚动
const scrollTargetPage = ref<number | null>(null) // 程序滚动目标页

// 点击/拖动检测相关
const mouseDownInfo = ref<{ x: number; y: number; time: number } | null>(null)
const CLICK_THRESHOLD = 5 // 移动距离小于此值视为点击
const CLICK_TIME_THRESHOLD = 300 // 点击时间小于此值视为点击（毫秒）

// 循环选择高亮相关
const highlightsAtCurrentPoint = ref<ReturnType<typeof pdfStore.getHighlightsAtPoint>>([])
const currentHighlightIndex = ref(0)

function handlePageContainerRef(
  pageNumber: number, // 当前页码
  ref: Element | ComponentPublicInstance | null, // Vue 传入的泛型引用
  _refs?: Record<string, Element | ComponentPublicInstance> // 备用的 refs 对象占位
) {
  const el = ref instanceof HTMLElement ? ref : null // 仅当 ref 为原生元素时才使用
  setPageRef(pageNumber, el) // 将合法引用交给内部处理
}

function setPageRef(pageNumber: number, el: HTMLElement | null) {
  if (!el) {
    pageRefs.delete(pageNumber) // 若元素不存在则移除缓存
    return
  }

  const canvas = el.querySelector('canvas') // 查找页面对应的画布
  const textLayer = el.querySelector('.textLayer') // 查找页面对应的文字图层
  const linkLayer = el.querySelector('.linkLayer') // 查找页面对应的链接图层

  if (canvas instanceof HTMLCanvasElement && textLayer instanceof HTMLDivElement && linkLayer instanceof HTMLDivElement) {
    pageRefs.set(pageNumber, {
      container: el, // 存储页面容器
      canvas, // 存储画布引用
      textLayer, // 存储文字层引用
      linkLayer // 存储链接层引用
    })
    // 移除立即渲染，改由 updateVisiblePages 统一调度
    // renderPage(pageNumber) 
  }
}

watch(
  () => pdfStore.currentPdfUrl, // 监听当前 PDF 地址
  (url) => {
    if (url) {
      loadPdf(url) // 地址存在则加载 PDF
    } else {
      console.log('No PDF URL provided.') // 调试日志
      cleanup() // 地址清空则重置状态
    }
  },
  { immediate: true }
)

// 核心渲染逻辑：仅渲染可见区域页面，大幅提升长文档性能
const updateVisiblePages = useDebounceFn(() => {
  if (!containerRef.value || !pdfDoc.value) return

  const container = containerRef.value
  const { top: containerTop, bottom: containerBottom } = container.getBoundingClientRect()
  const buffer = 200 // 视口上下预加载缓冲区

  const newVisiblePages = new Set<number>()

  pageRefs.forEach((refs, pageNumber) => {
    const { top, bottom } = refs.container.getBoundingClientRect()
    // 检查页面是否在视口范围内（包含缓冲区）
    if (top < containerBottom + buffer && bottom > containerTop - buffer) {
      newVisiblePages.add(pageNumber)
      // 如果之前未渲染或需要重绘，则触发渲染
      if (!renderTasks.has(pageNumber)) {
        renderPage(pageNumber)
      }
    }
  })

  visiblePages.clear()
  newVisiblePages.forEach(p => visiblePages.add(p))
}, 100)

watch(
  () => pdfStore.scale, // 监听缩放比例
  () => {
    // 缩放时清除所有现有任务并重新检测可见区域进行渲染
    renderTasks.forEach(task => task.cancel())
    renderTasks.clear()
    nextTick(() => {
      updateVisiblePages()
    })
  }
)

watch(
  () => pdfStore.currentPage, // 监听当前页号
  (page) => {
    isProgrammaticScrolling.value = true
    scrollTargetPage.value = page
    scrollToPage(page) // 页面变更时滚动到对应位置
    // 安全回退：3秒后强制释放，防止卡死
    setTimeout(() => {
      if (scrollTargetPage.value === page) {
        isProgrammaticScrolling.value = false
        scrollTargetPage.value = null
      }
    }, 3000)
  }
)

async function renderPage(pageNumber: number) {
  const pdf = pdfDoc.value // 当前文档实例
  const refs = pageRefs.get(pageNumber) // 当前页的引用集合
  if (!pdf || !refs) return // 缺失则跳过

  // 防止重复渲染同一页
  if(renderTasks.has(pageNumber)) return

  const page = await pdf.getPage(pageNumber) // 获取指定页
  const viewport = page.getViewport({ scale: pdfStore.scale }) // 依据缩放创建视口

  const context = refs.canvas.getContext('2d') // 获取画布 2D 上下文
  if (!context) return // 无上下文则终止

  // 1. 高清屏优化：获取设备像素比
  const outputScale = window.devicePixelRatio || 1

  // 2. 布局优化：设置容器与 Canvas 的逻辑尺寸和物理尺寸
  // 容器本身不需要设大，但内部 Canvas 需要根据 dpr 放大
  refs.container.style.width = `${Math.floor(viewport.width)}px`
  refs.container.style.height = `${Math.floor(viewport.height)}px`

  refs.canvas.width = Math.floor(viewport.width * outputScale)
  refs.canvas.height = Math.floor(viewport.height * outputScale)
  refs.canvas.style.width = `${Math.floor(viewport.width)}px`
  refs.canvas.style.height = `${Math.floor(viewport.height)}px`

  // 文字层和链接层使用逻辑尺寸
  refs.textLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.textLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.textLayer.style.setProperty('--scale-factor', `${viewport.scale}`)
  refs.textLayer.innerHTML = '' // 重绘前清空文字层
  
  // 链接层同样使用逻辑尺寸（复用 renderLinkLayer 内部逻辑，也可以在此显式重置防止闪烁）
  refs.linkLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.linkLayer.style.height = `${Math.floor(viewport.height)}px`

  // 3. 渲染优化：应用缩放变换
  const transform = outputScale !== 1 
    ? [outputScale, 0, 0, outputScale, 0, 0] 
    : undefined

  const renderTask = page.render({ 
    canvasContext: context, 
    viewport, 
    transform 
  }) // 创建页面渲染任务
  renderTasks.set(pageNumber, renderTask) // 缓存任务便于取消
  
  try {
    await renderTask.promise // 等待绘制完成
  } catch (err: any) {
    if (err.name === 'RenderingCancelledException') {
      // 忽略因取消导致的报错
      return
    }
    console.error(err)
  }
  
  // 仅任务未被取消时才继续渲染文本
  const textContent = await page.getTextContent() // 获取文字内容
  await renderTextLayer({
    textContentSource: textContent, // 提供文字内容
    container: refs.textLayer, // 指定文字层容器
    viewport, // 提供视口信息
    textDivs: [] // 文字节点数组占位
  }).promise // 等待文字层绘制完成

  try {
    const annotations = await page.getAnnotations()
    renderLinkLayer(annotations, viewport, refs.linkLayer, refs.textLayer)
  } catch (err) {
    console.error('Error rendering link layer:', err)
  }
}

type LinkOverlayRect = {
  left: number
  top: number
  width: number
  height: number
}

function normalizeUrl(raw: string): string | null {
  const trimmed = raw.trim().replace(/[),.;]+$/g, '') // 去掉末尾标点避免误判
  if (!trimmed) return null
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (/^www\./i.test(trimmed)) return `https://${trimmed}`
  return null
}

function appendLinkOverlay(container: HTMLElement, rect: LinkOverlayRect, href: string, title?: string) {
  const link = document.createElement('a')
  link.href = href
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

function appendInternalLinkOverlay(container: HTMLElement, rect: LinkOverlayRect, destPage: number, title?: string) {
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
    console.log('Jumping to page:', destPage)
    pdfStore.goToPage(destPage)
  })
  container.appendChild(link)
}

async function resolveDestination(dest: any): Promise<number | null> {
  if (!pdfDoc.value) return null

  try {
    let destArray = dest

    // 如果是命名目标（字符串），需要先解析
    if (typeof dest === 'string') {
      destArray = await pdfDoc.value.getDestination(dest)
    }

    if (!destArray || !Array.isArray(destArray)) return null

    // 目标数组的第一个元素是页面引用
    const pageRef = destArray[0]
    if (!pageRef) return null

    // 获取页码
    const pageIndex = await pdfDoc.value.getPageIndex(pageRef)
    return pageIndex + 1 // 转为1-based页码
  } catch (err) {
    console.error('Error resolving destination:', err)
    return null
  }
}

function renderTextUrlOverlays(textLayer: HTMLElement, container: HTMLElement) {
  const urlRegex = /\b((?:https?:\/\/|www\.)[^\s<>"'()]+[^\s<>"'().])/gi
  const layerRect = textLayer.getBoundingClientRect()
  const spans = Array.from(textLayer.querySelectorAll('span'))

  spans.forEach(span => {
    const textNode = span.firstChild
    const text = span.textContent || ''
    if (!textNode || !text) return

    let match: RegExpExecArray | null
    while ((match = urlRegex.exec(text)) !== null) {
      const href = normalizeUrl(match[0])
      if (!href) continue

      const range = document.createRange()
      range.setStart(textNode, match.index)
      range.setEnd(textNode, match.index + match[0].length)
      const rect = range.getBoundingClientRect()
      range.detach()

      if (!rect.width || !rect.height) continue

      appendLinkOverlay(
        container,
        {
          left: rect.left - layerRect.left,
          top: rect.top - layerRect.top,
          width: rect.width,
          height: rect.height
        },
        href,
        match[0]
      )
    }
  })
}

async function renderLinkLayer(annotations: any[], viewport: any, container: HTMLElement, textLayer?: HTMLElement) {
  container.innerHTML = '' // 清空链接层
  container.style.width = `${viewport.width}px` // 设置宽度
  container.style.height = `${viewport.height}px` // 设置高度

  for (const annotation of annotations) {
    if (annotation.subtype !== 'Link') continue

    const rect = viewport.convertToViewportRectangle(annotation.rect)
    const [x1, y1, x2, y2] = rect
    const overlayRect = {
      left: Math.min(x1, x2),
      top: Math.min(y1, y2),
      width: Math.abs(x2 - x1),
      height: Math.abs(y2 - y1)
    }

    if (annotation.url) {
      // 外部链接
      appendLinkOverlay(container, overlayRect, annotation.url, annotation.url || 'External Link')
    } else if (annotation.dest) {
      // 内部链接（如论文引用）
      const destPage = await resolveDestination(annotation.dest)
      if (destPage) {
        appendInternalLinkOverlay(container, overlayRect, destPage, `跳转到第 ${destPage} 页`)
      }
    } else if (annotation.action?.dest) {
      // 带action的内部链接
      const destPage = await resolveDestination(annotation.action.dest)
      if (destPage) {
        appendInternalLinkOverlay(container, overlayRect, destPage, `跳转到第 ${destPage} 页`)
      }
    }
  }

  // 从纯文本中额外检测 URL，生成可点击覆盖层
  if (textLayer) {
    renderTextUrlOverlays(textLayer, container)
  }
}

async function loadPdf(url: string) {
  cleanup() // 清理旧状态
  pdfStore.isLoading = true // 标记加载中

  // 配置 CMaps 以正确渲染中文字符
  const loadingTask = getDocument({
    url,
    cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
    cMapPacked: true
  })
  const pdf = await loadingTask.promise // 等待文档加载完成

  pdfDoc.value = pdf // 保存文档实例
  pdfStore.setTotalPages(pdf.numPages) // 更新总页数到状态
  if (libraryStore.currentDocumentId) {
    libraryStore.updateDocumentPageCount(libraryStore.currentDocumentId, pdf.numPages) // 同步更新文库记录页数
  }
  pageNumbers.value = Array.from({ length: pdf.numPages }, (_, index) => index + 1) // 构造页码数组

  pdfStore.isLoading = false // 结束加载态
  await nextTick() // 等待 DOM 更新
  updateVisiblePages() // 初始渲染可见页面
}

function cleanup() {
  renderTasks.forEach((task) => task.cancel()) // 取消未完成的渲染任务
  renderTasks.clear() // 清空任务缓存
  pageRefs.clear() // 清空页面引用缓存
  pageNumbers.value = [] // 清空页码列表
  pdfDoc.value = null // 释放文档实例
}

function handleMouseDown(event: MouseEvent) {
  // 记录鼠标按下位置和时间
  mouseDownInfo.value = {
    x: event.clientX,
    y: event.clientY,
    time: Date.now()
  }
}

function handleMouseUp(event: MouseEvent) {
  const downInfo = mouseDownInfo.value
  mouseDownInfo.value = null

  // 检查是否点击到了链接（链接优先级最高）
  const target = event.target as HTMLElement
  if (target.tagName === 'A' || target.closest('a') || target.classList.contains('internal-link') || target.closest('.internal-link')) {
    return // 让链接自己处理点击
  }

  // 判断是点击还是拖动
  const isClick = downInfo &&
    Math.abs(event.clientX - downInfo.x) < CLICK_THRESHOLD &&
    Math.abs(event.clientY - downInfo.y) < CLICK_THRESHOLD &&
    Date.now() - downInfo.time < CLICK_TIME_THRESHOLD

  if (isClick) {
    // 这是一个点击操作
    handleClick(event)
  } else {
    // 这是一个拖动选择操作
    handleTextSelection()
  }
}

function handleClick(event: MouseEvent) {
  // 查找点击位置对应的页面
  const pageEl = findPageElement(event.target as Node)
  if (!pageEl || !pageEl.dataset.page) {
    // 点击在页面外部，清除选择
    handleClickOutside()
    return
  }

  const pageNumber = Number(pageEl.dataset.page)
  const textLayer = pageEl.querySelector('.textLayer') as HTMLDivElement | null
  if (!textLayer) return

  const layerRect = textLayer.getBoundingClientRect()
  if (!layerRect.width || !layerRect.height) return

  // 计算归一化坐标
  const normalizedX = (event.clientX - layerRect.left) / layerRect.width
  const normalizedY = (event.clientY - layerRect.top) / layerRect.height

  // 查找该位置的所有高亮
  const highlightsAtPoint = pdfStore.getHighlightsAtPoint(pageNumber, normalizedX, normalizedY)

  if (highlightsAtPoint.length === 0) {
    // 点击的是未高亮区域，清除选择
    handleClickOutside()
    return
  }

  // 检查是否是同一位置的重复点击（循环选择）
  const isSamePoint = highlightsAtCurrentPoint.value.length > 0 &&
    highlightsAtCurrentPoint.value.some(h => highlightsAtPoint.some(hp => hp.id === h.id))

  if (isSamePoint && highlightsAtPoint.length > 1) {
    // 循环到下一个高亮
    currentHighlightIndex.value = (currentHighlightIndex.value + 1) % highlightsAtPoint.length
  } else {
    // 新位置，重置索引
    highlightsAtCurrentPoint.value = highlightsAtPoint
    currentHighlightIndex.value = 0
  }

  // 选中当前索引的高亮
  const selectedHighlight = highlightsAtPoint[currentHighlightIndex.value]
  if (!selectedHighlight) return

  // 计算高亮的显示位置（用于工具提示）
  const firstRect = selectedHighlight.rects[0]
  if (!firstRect) return

  const tooltipX = layerRect.left + (firstRect.left + firstRect.width / 2) * layerRect.width
  const tooltipY = layerRect.top + firstRect.top * layerRect.height - 10

  pdfStore.selectHighlight(selectedHighlight, { x: tooltipX, y: tooltipY })

  tooltipPosition.value = { x: tooltipX, y: tooltipY }
  showTooltip.value = true

  // 清除任何文本选择
  window.getSelection()?.removeAllRanges()
}

function handleTextSelection() {
  const selection = window.getSelection() // 获取当前窗口选择
  if (!selection || !selection.toString().trim()) return

  // 清除高亮选择状态
  pdfStore.clearHighlightSelection()

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
      height: rect.height / layerRect.height,
    }))
    .filter((rect) => rect.width > 0 && rect.height > 0)

  if (!rects.length) return

  // 过滤掉被包含的矩形（去除重复或嵌套的高亮）
  const uniqueRects = rects.filter((rect, index, self) => {
    return !self.some((other, otherIndex) => {
      if (index === otherIndex) return false

      const isSame = Math.abs(other.left - rect.left) < 0.001 &&
                     Math.abs(other.top - rect.top) < 0.001 &&
                     Math.abs(other.width - rect.width) < 0.001 &&
                     Math.abs(other.height - rect.height) < 0.001
      
      if (isSame) {
        // 如果完全相同，保留索引较小的那个
        return otherIndex < index
      }

      // 检查当前 rect 是否被 other 包含
      // 容差处理，避免浮点数精度问题
      const epsilon = 0.001
      const isContained = other.left <= rect.left + epsilon &&
                          other.top <= rect.top + epsilon &&
                          (other.left + other.width) >= (rect.left + rect.width) - epsilon &&
                          (other.top + other.height) >= (rect.top + rect.height) - epsilon
      return isContained
    })
  })

  const selectionRect = range.getBoundingClientRect() // 选区位置矩形

  pdfStore.setSelectedText(text, {
    x: selectionRect.left + selectionRect.width / 2,
    y: selectionRect.top - 10
  })
  pdfStore.setSelectionInfo({ page: pageNumber, rects: uniqueRects })

  tooltipPosition.value = {
    x: selectionRect.left + selectionRect.width / 2,
    y: selectionRect.top - 10
  }
  showTooltip.value = true // 打开提示
}

function handleClickOutside() {
  const selection = window.getSelection()
  // Keep the action menu open when there is still a text selection
  if (selection && selection.toString().trim()) return
  // Keep the menu open when editing a highlight
  if (pdfStore.isEditingHighlight) return

  showTooltip.value = false // 隐藏提示
  pdfStore.clearSelection() // 清空选中文本
  pdfStore.clearHighlightSelection() // 清空高亮选择
  highlightsAtCurrentPoint.value = []
  currentHighlightIndex.value = 0
}

function closeTooltip() {
  showTooltip.value = false
  pdfStore.clearSelection()
  pdfStore.clearHighlightSelection()
  highlightsAtCurrentPoint.value = []
  currentHighlightIndex.value = 0
}

function findPageElement(node: Node | null): HTMLElement | null {
  let current: Node | null = node
  while (current) {
    if (current instanceof HTMLElement && current.classList.contains('pdf-page')) {
      return current
    }
    current = current.parentElement || current.parentNode
  }
  return null
}

function hexToRgba(color: string, alpha = 0.35) {
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

function getHighlightColor(color: string) {
  return hexToRgba(color, 0.35)
}

function getBoundingBoxStyle(rects: { left: number, top: number, width: number, height: number }[]) {
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

  // 稍微扩展一点边距，让框看起来更像“包含”
  // 但既然是百分比，这里直接用计算出的边界
  return {
    left: `${minLeft * 100}%`,
    top: `${minTop * 100}%`,
    width: `${(maxRight - minLeft) * 100}%`,
    height: `${(maxBottom - minTop) * 100}%`
  }
}

function scrollToPage(page: number) {
  if (!containerRef.value) return // 无容器则返回
  const refs = pageRefs.get(page) // 获取目标页引用

  if (refs) {
    containerRef.value.scrollTo({
      top: refs.container.offsetTop - 12,
      behavior: 'smooth'
    })
    return
  }

  // 如果页面引用尚未准备好，等待下一次 DOM 更新后再尝试
  nextTick(() => {
    const retryRefs = pageRefs.get(page)
    if (retryRefs) {
      containerRef.value?.scrollTo({
        top: retryRefs.container.offsetTop - 12,
        behavior: 'smooth'
      })
    }
  })
}

function handleUserInteraction() {
  if (isProgrammaticScrolling.value) {
    isProgrammaticScrolling.value = false
    scrollTargetPage.value = null
  }
}

function handleScroll(){
  if (!containerRef.value) return // 无容器则返回

  updateVisiblePages() // 滚动时触发可见检测

  // 这里的 isProgrammaticScrolling 检查移到下面，结合 nearestPage 判断
  
  const pages = Array.from(containerRef.value.querySelectorAll('.pdf-page')) as HTMLElement[] // 收集所有页面元素
  if (!pages.length) return // 无页面则返回

  const containerTop = containerRef.value.getBoundingClientRect().top // 容器顶部位置
  let nearestPage = pdfStore.currentPage // 当前最近页初值
  let minDistance = Number.POSITIVE_INFINITY // 最小距离初值

  pages.forEach((pageEl, index) => {
    const distance = Math.abs(pageEl.getBoundingClientRect().top - containerTop) // 计算页面顶部与容器顶部距离
    if (distance < minDistance) {
      minDistance = distance // 更新最小距离
      nearestPage = index + 1 // 记录最近页号
    }
  })

  // 如果处于程序滚动模式
  if (isProgrammaticScrolling.value) {
    // 检查是否到达目标页
    if (scrollTargetPage.value !== null && nearestPage === scrollTargetPage.value) {
        // 到达目标，解除锁定
        isProgrammaticScrolling.value = false
        scrollTargetPage.value = null
    } else {
        // 未到达目标，忽略中间状态更新
        return
    }
  }

  if (nearestPage !== pdfStore.currentPage && nearestPage <= pdfStore.totalPages) {
    pdfStore.goToPage(nearestPage) // 同步状态中的当前页
  }
}


onBeforeUnmount(() => {
  cleanup() // 组件卸载前清理资源
})
</script>

<template>
  <!-- 组件根容器，纵向排列，占满可用高度 -->
  <div class="flex flex-col h-full bg-gray-100">
    <!-- 主内容区，显示 PDF 页面的滚动容器 -->
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="flex-1 overflow-auto p-4"
      @mousedown="handleMouseDown"
      @mouseup="handleMouseUp"
      @scroll="handleScroll"
      @wheel="handleUserInteraction"
      @touchstart="handleUserInteraction"
    >
      <!-- 居中内容区，控制最大宽度与行间距 -->
      <div class="space-y-4 flex flex-col items-center">
        <!-- 遍历所有页码生成页面容器 -->
        <div
          v-for="page in pageNumbers" 
          :key="page" 
          class="pdf-page relative bg-white shadow-lg border border-gray-200 overflow-hidden shrink-0" 
          :ref="(el, refs) => handlePageContainerRef(page, el, refs)" 
          :data-page="page"
        >
          <canvas class="block mx-auto" /> 
          <div class="highlightLayer absolute inset-0 pointer-events-none">
            <template v-for="hl in pdfStore.getHighlightsByPage(page)" :key="hl.id">
              <div
                v-for="(rect, idx) in hl.rects"
                :key="`${hl.id}-${idx}`"
                class="highlight-rect absolute pointer-events-none"
                :style="{
                  left: `${rect.left * 100}%`,
                  top: `${rect.top * 100}%`,
                  width: `${rect.width * 100}%`,
                  height: `${rect.height * 100}%`,
                  backgroundColor: getHighlightColor(hl.color)
                }"
              />
              <!-- 选中的高亮显示整体外包框 -->
              <div
                v-if="pdfStore.selectedHighlight?.id === hl.id"
                class="highlight-selected-box absolute pointer-events-none"
                :style="getBoundingBoxStyle(hl.rects)"
              />
            </template>
          </div>
          <div class="textLayer absolute inset-0" /> 
          <div class="linkLayer absolute inset-0" /> <!-- 链接层允许点击内部链接 -->
        </div>
      </div>
    </div>

    <!-- 当没有选择 PDF 时的占位提示 -->
    <div
      v-else
      class="flex-1 flex flex-col items-center justify-center text-gray-400"
    >
      <svg class="w-24 h-24 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"> <!-- 图标占位 -->
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> <!-- 文档图标路径 -->
      </svg>
      <h2 class="text-xl font-medium mb-2">开始阅读</h2> <!-- 标题文案 -->
      <p class="text-sm">从左侧上传 PDF 文件开始您的阅读之旅</p> <!-- 副标题提示 -->
    </div>

    <!-- 文字选中后的工具提示组件 -->
    <TextSelectionTooltip
      v-if="showTooltip && pdfStore.selectedText"
      :position="tooltipPosition"
      :text="pdfStore.selectedText"
      :mode="pdfStore.isEditingHighlight ? 'highlight' : 'selection'"
      :highlight="pdfStore.selectedHighlight"
      @close="closeTooltip"
    />
  </div>
</template>

<style scoped>
.pdf-page {
  border-radius: 0.75rem; /* 单页容器圆角 */
}

.textLayer {
  pointer-events: auto; /* 允许文字层响应鼠标事件 */
}

.highlightLayer {
  z-index: 1;
}

.linkLayer {
  z-index: 3;
  pointer-events: none; /* 让非链接区域透传，文本仍可选中 */
}

.highlight-rect {
  background: rgba(255, 235, 59, 0.4);
  border-radius: 4px;
}

.highlight-selected-box {
  border: 2px dashed #4a5568; /* 选中时显示的大框虚线边框 */
  box-shadow: 0 0 4px rgba(0,0,0,0.1);
  background-color: transparent;
  z-index: 2; /* 确保在普通高亮之上 */
}

:deep(.textLayer span) {
  cursor: text; /* 文字层中文字光标样式 */
}

:deep(.linkLayer a),
:deep(.linkLayer .internal-link) {
  pointer-events: auto; /* 仅链接可点击，其他区域透传 */
}
</style>
