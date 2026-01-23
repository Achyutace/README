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
import TranslationPanel from './TranslationPanel.vue' // 导入翻译面板组件

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
const pagesNeedingRefresh = new Set<number>() // 缩放后需要重绘的页面集合
const lastRenderedScale = new Map<number, number>() // 每页最后一次渲染使用的缩放比例
const pendingAnchor = ref<{ page: number; ratio: number } | null>(null) // 记录缩放前的视口锚点
const isPointerOverPdf = ref(false)
const isZooming = ref(false)

// 页面尺寸预加载（用于快速滚动时的占位）
const pageSizes = ref<Map<number, { width: number; height: number }>>(new Map())
// 已渲染完成的页面集合
const renderedPages = ref<Set<number>>(new Set())
const settleZooming = useDebounceFn(() => {
  isZooming.value = false
  updateVisiblePages()
  startBackgroundPreload()
}, 180)

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

function captureCenterAnchor() {
  const container = containerRef.value
  if (!container || !pageNumbers.value.length) return null

  const centerY = container.scrollTop + container.clientHeight / 2
  let anchor: { page: number; ratio: number } | null = null

  for (const page of pageNumbers.value) {
    const refs = pageRefs.get(page)
    if (!refs) continue
    const top = refs.container.offsetTop
    const height = refs.container.offsetHeight || refs.container.clientHeight
    if (!height) continue

    if (centerY >= top && centerY <= top + height) {
      anchor = { page, ratio: (centerY - top) / height }
      break
    }

    if (centerY > top) {
      anchor = { page, ratio: Math.min(1, Math.max(0, (centerY - top) / height)) }
    } else {
      anchor = { page, ratio: 0 }
      break
    }
  }

  return anchor
}

function restoreAnchor(anchor: { page: number; ratio: number }) {
  const container = containerRef.value
  if (!container) return

  const refs = pageRefs.get(anchor.page)
  if (!refs) {
    nextTick(() => {
      if (pendingAnchor.value) {
        restoreAnchor(pendingAnchor.value)
      }
    })
    return
  }

  const height = refs.container.offsetHeight || refs.container.clientHeight
  if (!height) return

  const targetTop = refs.container.offsetTop + anchor.ratio * height - container.clientHeight / 2
  container.scrollTo({
    top: targetTop,
    behavior: 'instant' as ScrollBehavior
  })
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
      const alreadyRendered = renderedPages.value.has(pageNumber)
      const needsRefresh = pagesNeedingRefresh.has(pageNumber)
      const shouldRenderNow = !alreadyRendered || (!isZooming.value && needsRefresh)

      // 如果之前未渲染或（缩放后）需要重绘且已结束缩放，则触发渲染
      if (shouldRenderNow && !renderTasks.has(pageNumber)) {
        renderPage(pageNumber, { preserveContent: alreadyRendered })
        pagesNeedingRefresh.delete(pageNumber)
      }
    }
  })

  visiblePages.clear()
  newVisiblePages.forEach(p => visiblePages.add(p))
}, 100)

watch(
  () => pdfStore.scale, // 监听缩放比例
  () => {
    pendingAnchor.value = captureCenterAnchor()

    isZooming.value = true

    // 取消当前预加载
    if (preloadAbortController) {
      preloadAbortController.abort()
      preloadAbortController = null
    }

    // 缩放时清除所有现有任务和已渲染状态，重新检测可见区域进行渲染
    renderTasks.forEach(task => task.cancel())
    renderTasks.clear()
    pagesNeedingRefresh.clear()
    pageRefs.forEach((_, pageNumber) => pagesNeedingRefresh.add(pageNumber))
    preloadProgress.value = 0

    applyInterimScale()

    nextTick(() => {
      updateVisiblePages()

      if (pendingAnchor.value) {
        nextTick(() => {
          if (pendingAnchor.value) {
            restoreAnchor(pendingAnchor.value)
            pendingAnchor.value = null
          }
        })
      }
      // 延迟重新启动预加载
      settleZooming()
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

async function renderPage(pageNumber: number, options?: { preserveContent?: boolean }) {
  const pdf = pdfDoc.value // 当前文档实例
  const refs = pageRefs.get(pageNumber) // 当前页的引用集合
  if (!pdf || !refs) return // 缺失则跳过

  // 防止重复渲染同一页
  if(renderTasks.has(pageNumber)) return

  const preserveContent = !!options?.preserveContent && renderedPages.value.has(pageNumber)

  const page = await pdf.getPage(pageNumber) // 获取指定页
  const viewport = page.getViewport({ scale: pdfStore.scale }) // 依据缩放创建视口

  const targetCanvas = preserveContent ? document.createElement('canvas') : refs.canvas
  const context = targetCanvas.getContext('2d') // 获取画布 2D 上下文
  if (!context) return // 无上下文则终止

  // 1. 高清屏优化：获取设备像素比
  const outputScale = window.devicePixelRatio || 1

  // 2. 布局优化：设置容器与 Canvas 的逻辑尺寸和物理尺寸
  // 容器本身不需要设大，但内部 Canvas 需要根据 dpr 放大
  refs.container.style.width = `${Math.floor(viewport.width)}px`
  refs.container.style.height = `${Math.floor(viewport.height)}px`

  targetCanvas.width = Math.floor(viewport.width * outputScale)
  targetCanvas.height = Math.floor(viewport.height * outputScale)
  targetCanvas.style.width = `${Math.floor(viewport.width)}px`
  targetCanvas.style.height = `${Math.floor(viewport.height)}px`

  // 文字层和链接层使用逻辑尺寸
  refs.textLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.textLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.textLayer.style.setProperty('--scale-factor', `${viewport.scale}`)
  refs.textLayer.style.transform = 'scale(1)'
  refs.textLayer.style.transformOrigin = 'top left'
  refs.textLayer.innerHTML = '' // 重绘前清空文字层
  
  // 链接层同样使用逻辑尺寸（复用 renderLinkLayer 内部逻辑，也可以在此显式重置防止闪烁）
  refs.linkLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.linkLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.linkLayer.style.transform = 'scale(1)'
  refs.linkLayer.style.transformOrigin = 'top left'

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

  if (preserveContent) {
    const destContext = refs.canvas.getContext('2d')
    if (destContext) {
      refs.canvas.width = targetCanvas.width
      refs.canvas.height = targetCanvas.height
      refs.canvas.style.width = targetCanvas.style.width
      refs.canvas.style.height = targetCanvas.style.height
      destContext.clearRect(0, 0, refs.canvas.width, refs.canvas.height)
      destContext.drawImage(targetCanvas, 0, 0)
    }
  }

  lastRenderedScale.set(pageNumber, pdfStore.scale)

  // 标记页面为已渲染完成（创建新 Set 以触发响应式更新）
  renderedPages.value = new Set([...renderedPages.value, pageNumber])
}

type LinkOverlayRect = {
  left: number
  top: number
  width: number
  height: number
}

// 统一清理 URL 内部空白字符（包含普通空格/不间断空格/零宽空格）
function sanitizeHref(href: string): string {
  return href.replace(/[\s\u00A0\u200B-\u200D\uFEFF]+/g, '')
}

// 返回修剪信息与最终 href：trimmed 为去除末尾非 URL 片段后的原始子串（不附加协议），href 为可点击链接
function normalizeUrlWithTrimInfo(raw: string): { trimmed: string | null; href: string | null } {
  let trimmed = raw.trim()

  // 去掉末尾标点避免误判
  trimmed = trimmed.replace(/[),.;:]+$/g, '')

  // 去除内部空白字符（有些 PDF 会在跨行时引入空格/零宽字符）
  trimmed = trimmed.replace(/[\s\u00A0\u200B-\u200D\uFEFF]+/g, '')

  // 关键修复：如果URL包含有效扩展名，截断扩展名之后的内容
  // 例如 "example.com/page.html.Y.Bengio" -> "example.com/page.html"
  // 例如 "example.com/page.htmlY" -> "example.com/page.html"
  const validExtPattern = /^(.*?\.(html?|pdf|php|aspx?|jsp|js|css|json|xml|txt|png|jpe?g|gif|svg|ico|zip|tar|gz|mp[34]|avi|mov|doc|xls|ppt|shtml))([^a-z].*)?$/i
  const extMatch = trimmed.match(validExtPattern)
  if (extMatch) {
    // 找到有效扩展名，检查后面是否有多余内容
    const afterExt = extMatch[3] || ''
    // 如果扩展名后面跟着非URL路径字符（如大写字母、点号等），截断
    if (afterExt && /^[.A-Z\s]/.test(afterExt)) {
      trimmed = extMatch[1] ?? trimmed
    }
  }

  // 修复PDF跨行URL问题：移除末尾错误包含的作者名或其他非URL内容
  // 模式1：数字后面跟着 .大写字母 结尾（作者引用开始，如 "1472.B"）
  trimmed = trimmed.replace(/(\d+[-\d]*)\.[A-Z]$/g, '$1')

  // 模式2：URL末尾有多个大写字母（可能是作者名缩写，如 ".ABC"）
  trimmed = trimmed.replace(/\.[A-Z]{1,3}$/g, '')

  // 模式3：末尾是 .单词 格式但单词不像是URL路径（如 ".Zhang", ".Smith"）
  const validExtensions = /\.(html?|pdf|php|aspx?|jsp|js|css|json|xml|txt|png|jpe?g|gif|svg|ico|zip|tar|gz|mp[34]|avi|mov|doc|xls|ppt|shtml)$/i
  if (!validExtensions.test(trimmed)) {
    // 如果末尾是 .单词 但不是常见扩展名，可能是误包含的作者名
    trimmed = trimmed.replace(/\.[A-Z][a-z]+$/g, '')
  }

  // 再次清理可能残留的末尾标点
  trimmed = trimmed.replace(/[),.;:]+$/g, '')

  // 移除末尾可能的空格和特殊字符
  trimmed = trimmed.replace(/[\s\u00A0]+$/g, '')

  if (!trimmed) return { trimmed: null, href: null }
  if (/^https?:\/\//i.test(trimmed)) return { trimmed, href: trimmed }
  if (/^www\./i.test(trimmed)) return { trimmed, href: `https://${trimmed}` }
  return { trimmed: null, href: null }
}

function appendLinkOverlay(container: HTMLElement, rect: LinkOverlayRect, href: string, title?: string) {
  const link = document.createElement('a')
  // 最终设置前移除 URL 内部空格，避免不可点击
  link.href = sanitizeHref(href)
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

function dedupeLinkOverlays(container: HTMLElement) {
  const anchors = Array.from(container.querySelectorAll('a')) as HTMLAnchorElement[]
  if (anchors.length < 2) return

  type AnchorInfo = {
    el: HTMLAnchorElement
    href: string
    rect: { left: number; top: number; width: number; height: number }
    area: number
    hrefLen: number
  }

  const infos: AnchorInfo[] = anchors.map(el => {
    const left = parseFloat(el.style.left || '0')
    const top = parseFloat(el.style.top || '0')
    const width = parseFloat(el.style.width || '0')
    const height = parseFloat(el.style.height || '0')
    const area = Math.max(0, width) * Math.max(0, height)
    const href = el.href || ''
    return { el, href, rect: { left, top, width, height }, area, hrefLen: href.length }
  })

  function overlapArea(a: AnchorInfo, b: AnchorInfo) {
    const ax2 = a.rect.left + a.rect.width
    const ay2 = a.rect.top + a.rect.height
    const bx2 = b.rect.left + b.rect.width
    const by2 = b.rect.top + b.rect.height
    const ow = Math.max(0, Math.min(ax2, bx2) - Math.max(a.rect.left, b.rect.left))
    const oh = Math.max(0, Math.min(ay2, by2) - Math.max(a.rect.top, b.rect.top))
    return ow * oh
  }

  function IoU(a: AnchorInfo, b: AnchorInfo) {
    const ov = overlapArea(a, b)
    const union = a.area + b.area - ov
    return union > 0 ? ov / union : 0
  }

  // function overlapFractions(small: AnchorInfo, big: AnchorInfo) {
  //   const sx2 = small.rect.left + small.rect.width
  //   const sy2 = small.rect.top + small.rect.height
  //   const bx2 = big.rect.left + big.rect.width
  //   const by2 = big.rect.top + big.rect.height
  //   const ow = Math.max(0, Math.min(sx2, bx2) - Math.max(small.rect.left, big.rect.left))
  //   const oh = Math.max(0, Math.min(sy2, by2) - Math.max(small.rect.top, big.rect.top))
  //   return {
  //     fracW: small.rect.width > 0 ? ow / small.rect.width : 0,
  //     fracH: small.rect.height > 0 ? oh / small.rect.height : 0,
  //   }
  // }

  const toRemove = new Set<HTMLAnchorElement>()
  for (let i = 0; i < infos.length; i++) {
    for (let j = i + 1; j < infos.length; j++) {
      const a = infos[i]
      const b = infos[j]
      if (!a || !b) continue
      if (a.area === 0 || b.area === 0) continue
      const iou = IoU(a, b)
      if( iou >= 0.3) {
        // 高覆盖度：删除较短的链接
        if (a.hrefLen < b.hrefLen) {
          toRemove.add(a.el)
        } else if (b.hrefLen < a.hrefLen) {
          toRemove.add(b.el)
        } else {
          // 长度相等时删除面积较小的
          if (a.area < b.area) {
            toRemove.add(a.el)
          } else {
            toRemove.add(b.el)
          }
        }
        continue
      }
    }
  }

  toRemove.forEach(el => el.remove())
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
  let lastSpan: { rect: DOMRect; text: string } | null = null

  spans.forEach(span => {
    const text = span.textContent || ''
    if (!text) return

    const rect = span.getBoundingClientRect()

    // 检测是否需要在span之间添加空格（真正的换行/分隔）
    if (lastSpan && fullText.length > 0) {
      const lineHeight = rect.height || 12
      const yGap = rect.top - lastSpan.rect.top

      // 判断是否是新的一行（Y坐标变化超过行高的一半）
      const isNewLine = yGap > lineHeight * 0.5

      // 判断X坐标是否连续（用于检测同一行内的断词）
      // 如果当前span的left接近上一个span的right，说明是连续的
      const xGap = rect.left - lastSpan.rect.right
      const isXContinuous = xGap < lineHeight * 0.5 && xGap > -lineHeight * 0.5

      // 检查上一个span是否以连字符结尾（PDF断词）
      const lastEndsWithHyphen = lastSpan.text.endsWith('-')

      // 检查是否是URL的延续部分（通常URL不会有空格）——此前使用字符类判断，现已由连接符与扩展名启发式替代

      // 检查当前span是否以文件扩展名开头（如 .html, .pdf 等）
      // 这通常是跨行URL的延续部分
      const startsWithExtension = /^\.(html?|pdf|php|aspx?|jsp|js|css|json|xml|txt|png|jpe?g|gif|svg|ico|zip|tar|gz|mp[34]|avi|mov|doc|xls|ppt|shtml)/i.test(text)

      // 连接符：URL 连续的明确信号
      const nextStartsWithConnector = /^[\/?#&=]/.test(text)
      const prevEndsWithConnector = /[\/?#&=]$/.test(lastSpan.text)
      const prevEndsWithKnownExt = /\.(html?|pdf|php|aspx?|jsp|js|css|json|xml|txt|png|jpe?g|gif|svg|ico|zip|tar|gz|mp[34]|avi|mov|doc|xls|ppt|shtml)$/.test(lastSpan.text)

      // 检查fullText是否看起来像是一个未完成的URL
      const looksLikeIncompleteUrl = /https?:\/\/[^\s]*$/.test(fullText) || /www\.[^\s]*$/.test(fullText)

      // 决定是否添加空格：
      // 1. 如果是新行且X不连续，通常需要空格（除非是URL延续）
      // 2. 如果上一个以连字符结尾，这是PDF断词，不加空格
      // 3. 如果末尾是点号后紧跟大写字母（作者引用开始），需要空格
      // 4. 如果当前span以文件扩展名开头且上一个像未完成的URL，不加空格
      const isAuthorCitation = /\.$/.test(lastSpan.text) && /^[A-Z]/.test(text) && !startsWithExtension
      // 标题或页码行（例如“1.”、“1.1 ”或纯页码）
      const isHeadingLike = /^\s*\d+(?:\.\d+)*(?:\s|$)/.test(text)
      const isPageNumberLine = /^\s*\d+\s*$/.test(text)

      let needsSpace = false
      if (isNewLine) {
        // 新行：如果X不连续/引用开始/标题或页码，添加空格
        if (!isXContinuous || isAuthorCitation || isHeadingLike || isPageNumberLine) {
          needsSpace = true
        }
        // 如果是连字符断词，不加空格
        if (lastEndsWithHyphen) {
          needsSpace = false
          // 移除末尾的连字符
          fullText = fullText.slice(0, -1)
        }
        // 扩展名开头且前面是未完成的URL：不加空格（URL跨行延续）
        if (startsWithExtension && looksLikeIncompleteUrl) {
          needsSpace = false
        }
        // 明确的 URL 连续信号：连接符相连，不加空格
        if (looksLikeIncompleteUrl && (nextStartsWithConnector || prevEndsWithConnector)) {
          needsSpace = false
        }
        // 如果上一段已是已知扩展名结尾，且下一段不是连接符开头，则视为句末，保持空格
        if (prevEndsWithKnownExt && !nextStartsWithConnector) {
          needsSpace = true
        }
      }

      // 兜底：上一段看起来是完整 URL，且下一段跳回左侧并以大写开头时，强制断开，防止把新段首词吞进 URL
      const prevLooksLikeUrl = /(https?:\/\/|www\.)\S+$/.test(fullText)
      const nextStartsWithUpper = /^[A-Z]/.test(text)
      const resetsToLeft = xGap < -lineHeight * 0.8
      if (!needsSpace && prevLooksLikeUrl && nextStartsWithUpper && resetsToLeft && !startsWithExtension && !nextStartsWithConnector) {
        needsSpace = true
      }

      if (needsSpace && !fullText.endsWith(' ') && !text.startsWith(' ')) {
        fullText += ' '
      }
    }

    lastSpan = { rect, text }

    spanInfos.push({
      span,
      text,
      globalStart: fullText.length,
      globalEnd: fullText.length + text.length
    })
    fullText += text
  })

  // 使用字符级状态机扫描URL，避免依赖正则匹配
  const isUrlChar = (ch: string) => /[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]/.test(ch)
  const startsWithInsensitive = (s: string, i: number, token: string) => s.substr(i, token.length).toLowerCase() === token
  const isWhitespace = (ch: string) => /\s/.test(ch)
  const isNoisePunct = (ch: string) => ch === ':' || ch === '：'
  const knownTlds = new Set([
    'com','net','org','edu','gov','io','ai','cn','uk','us','de','fr','jp','ru','xyz','site','info','dev','app','tech','me','tv','cc','co','ac'
  ])

  function tryBridgeTld(start: number, lastIncluded: number, j: number): { bridged: boolean; newLast: number; newJ: number } {
    // 仅当当前已收集片段末尾是 . + 1-2 字母时，尝试跨越噪声补全顶级域
    const pre = fullText.slice(start, Math.min(lastIncluded + 1, n))
    const m = pre.match(/\.([A-Za-z]{1,2})$/)
    if (!m) return { bridged: false, newLast: lastIncluded, newJ: j }
    const partial = (m[1] || '').toLowerCase()

    // 跳过少量噪声（空白与中/英文冒号），防止误跳太远
    let k = j
    let skipped = 0
    while (k < n && (isWhitespace(fullText.charAt(k)) || isNoisePunct(fullText.charAt(k)))) {
      k++
      skipped++
      if (skipped > 4) break
    }
    if (k >= n) return { bridged: false, newLast: lastIncluded, newJ: j }

    // 尝试用已知 TLD 补全，例如 .n + et → .net；.co + m → .com
    for (const tld of knownTlds) {
      if (!tld.startsWith(partial)) continue
      const need = tld.slice(partial.length)
      if (!need) continue
      const nextSlice = fullText.substr(k, need.length).toLowerCase()
      if (nextSlice === need) {
        const newLast = k + need.length - 1
        const newJ = newLast + 1
        return { bridged: true, newLast, newJ }
      }
    }
    return { bridged: false, newLast: lastIncluded, newJ: j }
  }

  const collectUrls: Array<{ start: number; end: number; raw: string; href: string }> = []
  let i = 0
  const n = fullText.length
  while (i < n) {
    // 查找 URL 起点
    if (
      (i + 7 <= n && startsWithInsensitive(fullText, i, 'http://')) ||
      (i + 8 <= n && startsWithInsensitive(fullText, i, 'https://')) ||
      (i + 4 <= n && startsWithInsensitive(fullText, i, 'www.'))
    ) {
      const start = i
      let j = i
      let lastIncluded = i
      // 快速跳过起始协议/前缀
      if (startsWithInsensitive(fullText, j, 'https://')) j += 8
      else if (startsWithInsensitive(fullText, j, 'http://')) j += 7
      else if (startsWithInsensitive(fullText, j, 'www.')) j += 4
      lastIncluded = j - 1

      // 消费后续字符：允许URL字符；遇到空白则跳过继续（跨行合并）
      while (j < n) {
        const ch = fullText.charAt(j)
        if (isUrlChar(ch)) {
          lastIncluded = j
          j++
          continue
        }
        // 碰到空白或噪声标点：优先尝试“跨噪声补全TLD”，否则终止URL
        if (isWhitespace(ch) || isNoisePunct(ch)) {
          const bridged = tryBridgeTld(start, lastIncluded, j)
          if (bridged.bridged) {
            lastIncluded = bridged.newLast
            j = bridged.newJ
            continue
          }
          break
        }
        // 其他非URL字符，终止URL
        break
      }

      // 生成原始片段并进行末尾修剪
      const rawMatch = fullText.slice(start, lastIncluded + 1)
      const { trimmed, href } = normalizeUrlWithTrimInfo(rawMatch)
      if (href && trimmed) {
        // 回退末尾被修剪的字符数，确保覆盖层不吞下一行首字
        const endTrimCount = rawMatch.length - trimmed.length
        const urlEnd = (lastIncluded + 1) - (endTrimCount > 0 ? endTrimCount : 0)
        collectUrls.push({ start, end: urlEnd, raw: rawMatch, href })
      }
      i = j
      continue
    }
    i++
  }

  // 将收集到的URL映射为覆盖层
  for (const u of collectUrls) {
    const urlStart = u.start
    const urlEnd = u.end
    const affectedSpans = spanInfos.filter(info => info.globalEnd > urlStart && info.globalStart < urlEnd)
    affectedSpans.forEach(info => {
      const textNode = info.span.firstChild
      if (!textNode) return
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
        appendLinkOverlay(
          container,
          {
            left: rect.left - layerRect.left,
            top: rect.top - layerRect.top,
            width: rect.width,
            height: rect.height
          },
          u.href,
          u.raw
        )
      } catch {}
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
    // 渲染完成后，对重叠或前缀重复的链接做去重，保留更完整的覆盖层
    dedupeLinkOverlays(container)
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
  pagesNeedingRefresh.clear()
  lastRenderedScale.clear()
  isZooming.value = false
  pdfDoc.value = null // 释放文档实例
}

// 缩放手势进行时，先按目标尺寸拉伸已有渲染，避免立即显示占位符
function applyInterimScale() {
  pageRefs.forEach((refs, pageNumber) => {
    const size = pageSizes.value.get(pageNumber)
    if (!size) return

    const targetWidth = Math.floor(size.width * pdfStore.scale)
    const targetHeight = Math.floor(size.height * pdfStore.scale)
    const renderedScale = lastRenderedScale.get(pageNumber) ?? pdfStore.scale
    const ratio = renderedScale ? pdfStore.scale / renderedScale : 1

    refs.canvas.style.width = `${targetWidth}px`
    refs.canvas.style.height = `${targetHeight}px`

    refs.textLayer.style.width = `${targetWidth}px`
    refs.textLayer.style.height = `${targetHeight}px`
    refs.textLayer.style.transformOrigin = 'top left'
    refs.textLayer.style.transform = `scale(${ratio})`

    refs.linkLayer.style.width = `${targetWidth}px`
    refs.linkLayer.style.height = `${targetHeight}px`
    refs.linkLayer.style.transformOrigin = 'top left'
    refs.linkLayer.style.transform = `scale(${ratio})`
  })
}

function handleMouseEnterContainer() {
  isPointerOverPdf.value = true
}

function handleMouseLeaveContainer() {
  isPointerOverPdf.value = false
}

function handleWheel(event: WheelEvent) {
  // Trackpad pinch on Chrome/Edge reports wheel with ctrlKey=true; intercept only inside PDF.
  if (!isPointerOverPdf.value) return
  if (!event.ctrlKey) return

  event.preventDefault()
  event.stopPropagation()

  const delta = event.deltaY
  const step = Math.min(0.25, Math.max(0.05, Math.abs(delta) / 500))
  const nextScale = delta < 0
    ? Math.min(3.0, pdfStore.scale + step)
    : Math.max(0.5, pdfStore.scale - step)

  pdfStore.setScale(nextScale)
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

// 点击段落光标，打开翻译面板
function handleParagraphMarkerClick(event: MouseEvent, paragraphId: string, originalText: string) {
  event.stopPropagation()
  event.preventDefault()
  
  // 获取光标元素位置，计算翻译面板位置（显示在右侧）
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  
  // 默认显示在段落右边
  const panelX = rect.right + 10
  const panelY = rect.top
  
  // 如果右边空间不足，显示在左边
  const panelWidth = 320
  const finalX = (panelX + panelWidth > window.innerWidth) ? (rect.left - panelWidth - 10) : panelX
  
  pdfStore.openTranslationPanel(paragraphId, { x: Math.max(0, finalX), y: Math.max(0, panelY) }, originalText)
}

// 计算段落光标在页面中的位置（考虑缩放）
function getParagraphMarkerStyle(paragraph: { bbox: { x0: number; y0: number } }, pageNumber: number) {
  const size = pageSizes.value.get(pageNumber)
  if (!size) return { display: 'none' }
  
  // 光标显示在段落左上角
  const left = (paragraph.bbox.x0 / size.width) * 100
  const top = (paragraph.bbox.y0 / size.height) * 100
  
  return {
    left: `${left}%`,
    top: `${top}%`,
    transform: 'translate(-100%, -50%)'
  }
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
  <div class="pdf-viewer-root flex flex-col h-full bg-gray-100 dark:bg-[#0b1220] relative">
    <!-- 主内容区，显示 PDF 页面的滚动容器 -->
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="pdf-scroll-container flex-1 overflow-auto p-4"
      @mouseenter="handleMouseEnterContainer"
      @mouseleave="handleMouseLeaveContainer"
      @mousedown="handleMouseDown"
      @mouseup="handleMouseUp"
      @wheel="handleWheel"
      @scroll="handleScroll"
    >
      <!-- 居中内容区，控制最大宽度与行间距 -->
      <div class="space-y-4 flex flex-col items-center">
        <!-- 遍历所有页码生成页面容器 -->
        <div
          v-for="page in pageNumbers"
          :key="page"
          class="pdf-page relative bg-white dark:bg-[#111827] shadow-lg dark:shadow-[0_10px_30px_rgba(0,0,0,0.45)] border border-gray-200 dark:border-[#1f2937] overflow-hidden shrink-0"
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
            class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50 dark:bg-[#0f172a] z-10"
          >
            <div class="loading-spinner mb-3"></div>
            <span class="text-gray-400 text-sm">{{ page }}</span>
          </div>
          <canvas class="block mx-auto" />
          <div class="highlightLayer absolute inset-0 pointer-events-none" :class="{ 'zooming-layer': isZooming }">
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
          <div class="textLayer absolute inset-0" :class="{ 'zooming-layer': isZooming }" /> 
          <div class="linkLayer absolute inset-0" :class="{ 'zooming-layer': isZooming }" /> <!-- 链接层允许点击内部链接 -->
          
          <!-- 段落光标层 -->
          <div class="paragraphMarkerLayer absolute inset-0 pointer-events-none z-10" :class="{ 'zooming-layer': isZooming }">
            <div
              v-for="paragraph in pdfStore.getParagraphsByPage(page)"
              :key="paragraph.id"
              :data-paragraph-id="paragraph.id"
              class="paragraph-marker absolute pointer-events-auto cursor-pointer"
              :style="getParagraphMarkerStyle(paragraph, page)"
              @click="handleParagraphMarkerClick($event, paragraph.id, paragraph.content)"
              :title="'点击翻译此段落'"
            >
              <div class="marker-icon">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                </svg>
              </div>
            </div>
          </div>
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
    
    <!-- 翻译面板（可拖动，位于最上层） -->
    <TranslationPanel />
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

/* 段落光标层 */
.paragraphMarkerLayer {
  z-index: 5;
}

/* 段落光标样式 */
.paragraph-marker {
  z-index: 6;
}

.paragraph-marker .marker-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.4);
  transition: all 0.2s ease;
  opacity: 0.85;
}

.paragraph-marker:hover .marker-icon {
  opacity: 1;
  transform: scale(1.15);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
}

.paragraph-marker .marker-icon svg {
  width: 12px;
  height: 12px;
}

.zooming-layer {
  opacity: 0.35;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

/* Dark mode adjustments: dark canvas and white text for comfortable reading */
:global(.dark .pdf-viewer-root) {
  background: #0b1220;
}

:global(.dark .pdf-scroll-container) {
  background: #0b1220;
}

:global(.dark .pdf-page) {
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
}

:global(.dark .pdf-page canvas) {
  background-color: #111827;
  filter: invert(0.92) hue-rotate(180deg) brightness(1.05);
}

:global(.dark .textLayer),
:global(.dark .textLayer span) {
  color: #0b0b0b !important;
  mix-blend-mode: normal;
}

:global(.dark .highlight-selected-box) {
  border-color: #cbd5ff;
}

:global(.dark .loading-spinner) {
  border-color: #1f2937;
  border-top-color: #9ca3af;
}
</style>
