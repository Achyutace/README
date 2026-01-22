<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch, type ComponentPublicInstance } from 'vue' // 引入 Vue 核心 API 与组件实例类型
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

// 页面尺寸预加载（用于快速滚动时的占位）
const pageSizes = ref<Map<number, { width: number; height: number }>>(new Map())
// 已渲染完成的页面集合
const renderedPages = ref<Set<number>>(new Set())

const showTooltip = ref(false) // 是否显示选中文本的工具提示
const tooltipPosition = ref({ x: 0, y: 0 }) // 工具提示的坐标

// 后台预加载相关
const preloadProgress = ref(0) // 预加载进度 (0-100)
const isPreloading = ref(false) // 是否正在预加载
let preloadAbortController: AbortController | null = null // 用于取消预加载

// 点击/拖动检测相关
const mouseDownInfo = ref<{ x: number; y: number; time: number } | null>(null)
const CLICK_THRESHOLD = 5 // 移动距离小于此值视为点击
const CLICK_TIME_THRESHOLD = 300 // 点击时间小于此值视为点击（毫秒）

// 循环选择高亮相关
const highlightsAtCurrentPoint = ref<ReturnType<typeof pdfStore.getHighlightsAtPoint>>([])
const currentHighlightIndex = ref(0)

// 容器尺寸变化监听（用于面板收起/展开时保持页面位置）
let resizeObserver: ResizeObserver | null = null
let resizeTimeout: ReturnType<typeof setTimeout> | null = null
const isResizing = ref(false)

// 获取指定页面的缩放后尺寸
function getScaledPageSize(pageNumber: number) {
  const size = pageSizes.value.get(pageNumber)
  if (!size) return { width: 612, height: 792 } // 默认 A4 尺寸
  return {
    width: Math.floor(size.width * pdfStore.scale),
    height: Math.floor(size.height * pdfStore.scale)
  }
}

// 检查页面是否已渲染
function isPageRendered(pageNumber: number) {
  return renderedPages.value.has(pageNumber)
}

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
    // 切换文档时重置UI状态
    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0

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
    // 取消当前预加载
    if (preloadAbortController) {
      preloadAbortController.abort()
      preloadAbortController = null
    }

    // 缩放时清除所有现有任务和已渲染状态，重新检测可见区域进行渲染
    renderTasks.forEach(task => task.cancel())
    renderTasks.clear()
    renderedPages.value = new Set() // 清空已渲染页面，因为缩放后需要重新渲染
    preloadProgress.value = 0

    nextTick(() => {
      updateVisiblePages()
      // 延迟重新启动预加载
      setTimeout(() => {
        startBackgroundPreload()
      }, 500)
    })
  }
)

// 监听工具栏触发的页面跳转（仅响应用户主动跳转，不自动触发）
let lastUserTriggeredPage = 1
watch(
  () => pdfStore.currentPage,
  (page, oldPage) => {
    // 只有当页码变化且不是由滚动触发时才跳转
    // 通过比较 lastUserTriggeredPage 来判断是否是用户主动跳转
    if (page !== oldPage && page !== lastUserTriggeredPage) {
      lastUserTriggeredPage = page
      scrollToPage(page, true) // 使用 instant 滚动
    }
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

  // 标记页面为已渲染完成（创建新 Set 以触发响应式更新）
  renderedPages.value = new Set([...renderedPages.value, pageNumber])
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

  // 收集所有span的信息：文本内容、起始位置、元素引用
  type SpanInfo = {
    span: HTMLElement
    text: string
    globalStart: number // 在合并文本中的起始位置
    globalEnd: number   // 在合并文本中的结束位置
  }

  const spanInfos: SpanInfo[] = []
  let fullText = ''

  spans.forEach(span => {
    const text = span.textContent || ''
    if (!text) return

    spanInfos.push({
      span,
      text,
      globalStart: fullText.length,
      globalEnd: fullText.length + text.length
    })
    fullText += text
  })

  // 在合并后的完整文本中匹配URL
  let match: RegExpExecArray | null
  while ((match = urlRegex.exec(fullText)) !== null) {
    const urlStart = match.index
    const urlEnd = match.index + match[0].length
    const fullUrl = match[0]
    const href = normalizeUrl(fullUrl)
    if (!href) continue

    // 找出这个URL跨越了哪些span
    const affectedSpans = spanInfos.filter(info =>
      info.globalEnd > urlStart && info.globalStart < urlEnd
    )

    // 为每个受影响的span创建对应的链接覆盖层
    affectedSpans.forEach(info => {
      const textNode = info.span.firstChild
      if (!textNode) return

      // 计算这个span中URL部分的本地偏移
      const localStart = Math.max(0, urlStart - info.globalStart)
      const localEnd = Math.min(info.text.length, urlEnd - info.globalStart)

      if (localStart >= localEnd) return

      try {
        const range = document.createRange()
        range.setStart(textNode, localStart)
        range.setEnd(textNode, localEnd)
        const rect = range.getBoundingClientRect()
        range.detach()

        if (!rect.width || !rect.height) return

        // 所有行都使用完整的URL作为href
        appendLinkOverlay(
          container,
          {
            left: rect.left - layerRect.left,
            top: rect.top - layerRect.top,
            width: rect.width,
            height: rect.height
          },
          href,
          fullUrl // title显示完整URL
        )
      } catch (e) {
        // 忽略range设置失败的情况
      }
    })
  }
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

  // 预加载所有页面的尺寸信息（用于快速滚动时的占位）
  const sizes = new Map<number, { width: number; height: number }>()
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i)
    const viewport = page.getViewport({ scale: 1 }) // 使用 scale=1 获取原始尺寸
    sizes.set(i, { width: viewport.width, height: viewport.height })
  }
  pageSizes.value = sizes

  pageNumbers.value = Array.from({ length: pdf.numPages }, (_, index) => index + 1) // 构造页码数组

  pdfStore.isLoading = false // 结束加载态
  await nextTick() // 等待 DOM 更新

  // 先渲染可见页面，然后启动后台预加载
  updateVisiblePages()

  // 延迟启动后台预加载，让可见页面优先渲染
  setTimeout(() => {
    startBackgroundPreload()
  }, 500)
}

// 后台预加载所有页面
async function startBackgroundPreload() {
  const pdf = pdfDoc.value
  if (!pdf) return

  // 取消之前的预加载
  if (preloadAbortController) {
    preloadAbortController.abort()
  }
  preloadAbortController = new AbortController()
  const signal = preloadAbortController.signal

  isPreloading.value = true
  preloadProgress.value = 0

  const totalPages = pdf.numPages
  let loadedCount = 0

  // 按顺序预加载所有页面
  for (let pageNumber = 1; pageNumber <= totalPages; pageNumber++) {
    if (signal.aborted) break

    // 如果页面已经渲染过，跳过
    if (renderedPages.value.has(pageNumber)) {
      loadedCount++
      preloadProgress.value = Math.round((loadedCount / totalPages) * 100)
      continue
    }

    // 等待 DOM 元素准备好
    const refs = pageRefs.get(pageNumber)
    if (refs && !renderTasks.has(pageNumber)) {
      // 使用 requestIdleCallback 或 setTimeout 在空闲时渲染
      await new Promise<void>((resolve) => {
        if ('requestIdleCallback' in window) {
          requestIdleCallback(() => {
            if (!signal.aborted) {
              renderPage(pageNumber)
            }
            resolve()
          }, { timeout: 100 })
        } else {
          setTimeout(() => {
            if (!signal.aborted) {
              renderPage(pageNumber)
            }
            resolve()
          }, 10)
        }
      })

      // 等待渲染完成
      await new Promise(resolve => setTimeout(resolve, 50))
    }

    loadedCount++
    preloadProgress.value = Math.round((loadedCount / totalPages) * 100)
  }

  isPreloading.value = false
  preloadProgress.value = 100
}

function cleanup() {
  // 取消后台预加载
  if (preloadAbortController) {
    preloadAbortController.abort()
    preloadAbortController = null
  }
  isPreloading.value = false
  preloadProgress.value = 0

  renderTasks.forEach((task) => task.cancel()) // 取消未完成的渲染任务
  renderTasks.clear() // 清空任务缓存
  pageRefs.clear() // 清空页面引用缓存
  pageNumbers.value = [] // 清空页码列表
  pageSizes.value = new Map() // 清空页面尺寸缓存
  renderedPages.value = new Set() // 清空已渲染页面集合
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

function scrollToPage(page: number, instant: boolean = false) {
  if (!containerRef.value) return // 无容器则返回
  const refs = pageRefs.get(page) // 获取目标页引用
  const behavior = instant ? 'instant' : 'smooth'

  if (refs) {
    containerRef.value.scrollTo({
      top: refs.container.offsetTop - 12,
      behavior: behavior as ScrollBehavior
    })
    return
  }

  // 如果页面引用尚未准备好，等待下一次 DOM 更新后再尝试
  nextTick(() => {
    const retryRefs = pageRefs.get(page)
    if (retryRefs) {
      containerRef.value?.scrollTo({
        top: retryRefs.container.offsetTop - 12,
        behavior: behavior as ScrollBehavior
      })
    }
  })
}

// 滚动处理：仅更新页码显示，不触发自动跳转
const handleScroll = useDebounceFn(() => {
  if (!containerRef.value) return

  updateVisiblePages() // 滚动时触发可见检测

  // 计算当前可见的页面
  const pages = Array.from(containerRef.value.querySelectorAll('.pdf-page')) as HTMLElement[]
  if (!pages.length) return

  const containerTop = containerRef.value.getBoundingClientRect().top
  let nearestPage = pdfStore.currentPage
  let minDistance = Number.POSITIVE_INFINITY

  pages.forEach((pageEl, index) => {
    const distance = Math.abs(pageEl.getBoundingClientRect().top - containerTop)
    if (distance < minDistance) {
      minDistance = distance
      nearestPage = index + 1
    }
  })

  // 仅更新页码显示，不触发滚动（通过更新 lastUserTriggeredPage 防止 watch 触发滚动）
  if (nearestPage !== pdfStore.currentPage && nearestPage <= pdfStore.totalPages) {
    lastUserTriggeredPage = nearestPage
    pdfStore.goToPage(nearestPage)
  }
}, 50)


// 设置容器尺寸变化监听器
onMounted(() => {
  // 等待DOM渲染完成后设置ResizeObserver
  nextTick(() => {
    if (!containerRef.value) return

    resizeObserver = new ResizeObserver(() => {
      // 容器尺寸变化时，标记为正在resize
      if (!isResizing.value && pdfDoc.value) {
        isResizing.value = true
      }

      // 清除之前的timeout
      if (resizeTimeout) {
        clearTimeout(resizeTimeout)
      }

      // 延迟后更新可见页面渲染
      resizeTimeout = setTimeout(() => {
        if (isResizing.value) {
          updateVisiblePages()
          isResizing.value = false
        }
      }, 150)
    })

    resizeObserver.observe(containerRef.value)
  })
})

onBeforeUnmount(() => {
  // 清理ResizeObserver
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
    resizeTimeout = null
  }
  cleanup() // 组件卸载前清理资源
})
</script>

<template>
  <!-- 组件根容器，纵向排列，占满可用高度 -->
  <div class="flex flex-col h-full bg-gray-100 relative">
    <!-- 预加载进度条 -->
    <div
      v-if="isPreloading && preloadProgress < 100"
      class="absolute top-0 left-0 right-0 z-20 h-1 bg-gray-200"
    >
      <div
        class="h-full bg-blue-500 transition-all duration-300"
        :style="{ width: preloadProgress + '%' }"
      ></div>
    </div>
    <!-- 主内容区，显示 PDF 页面的滚动容器 -->
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="flex-1 overflow-auto p-4"
      @mousedown="handleMouseDown"
      @mouseup="handleMouseUp"
      @scroll="handleScroll"
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
          :style="{
            width: getScaledPageSize(page).width + 'px',
            height: getScaledPageSize(page).height + 'px'
          }"
        >
          <!-- 加载中占位符 -->
          <div
            v-if="!isPageRendered(page)"
            class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 z-10"
          >
            <div class="loading-spinner mb-3"></div>
            <span class="text-gray-400 text-sm">{{ page }}</span>
          </div>
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

/* 加载动画 */
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e5e7eb;
  border-top-color: #6b7280;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
