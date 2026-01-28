<script setup lang="ts">
/*
----------------------------------------------------------------------
                            Pdf 查看器组件
----------------------------------------------------------------------
*/ 

// ------------------------- 导入依赖与组件 -------------------------
// 引入 Vue 核心 API、第三方工具及子组件
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch, type ComponentPublicInstance } from 'vue' 
import { useDebounceFn } from '@vueuse/core' 
import {
  getDocument,
  GlobalWorkerOptions,
  renderTextLayer,
  type PDFDocumentProxy,
  type RenderTask,
} from 'pdfjs-dist' 
import 'pdfjs-dist/web/pdf_viewer.css' 

// 引入 pdf.js worker
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.js?url' 
import { usePdfStore } from '../../stores/pdf' 
import { useLibraryStore } from '../../stores/library' 
import { notesApi, type Note } from '../../api' 
import TextSelectionTooltip from './TextSelectionTooltip.vue' 
import TranslationPanelMulti from './TranslationPanelMulti.vue' 
import NotePreviewCard from './NotePreviewCard.vue' 

GlobalWorkerOptions.workerSrc = pdfWorker // 设置 pdf.js 全局 worker 路径

// 每一页的元素定义
// 包含 页面容器、Canvas 层、Text 层和 Link 层
type PageRef = {
  container: HTMLElement // 页面容器元素引用
  canvas: HTMLCanvasElement // 页面绘制的画布引用
  textLayer: HTMLDivElement // 文字图层容器引用
  linkLayer: HTMLDivElement // 链接图层容器引用
  highlightLayer: HTMLDivElement // 高亮图层容器引用
}

// ------------------------- 初始化 store 实例 -------------------------
// 获取 store 实例
const pdfStore = usePdfStore() 
const libraryStore = useLibraryStore() 

// ------------------------- 初始化 PDF 状态与引用 -------------------------
// 滚动条
const containerRef = ref<HTMLElement | null>(null) 

// 当前 PDF 文档实例
const pdfDoc = shallowRef<PDFDocumentProxy | null>(null) 

// 页面序号集合
const pageNumbers = ref<number[]>([]) 

// 每页元素引用集合
const pageRefs = new Map<number, PageRef>() 

// 每页渲染任务集合
const renderTasks = new Map<number, RenderTask>() 

// 当前可见页面集合
const visiblePages = new Set<number>()

// 缩放后需要重绘的页面集合
const pagesNeedingRefresh = new Set<number>()

// 每页最后一次渲染使用的缩放比例
const lastRenderedScale = new Map<number, number>() 

// 缩放锚点：包含页码、垂直/水平比例、以及目标回复的屏幕坐标（可选）
type ZoomAnchor = {
  page: number
  ratioY: number
  ratioX: number
  destX?: number // 鼠标缩放时的目标屏幕X
  destY?: number // 鼠标缩放时的目标屏幕Y
}

// 当前待处理的缩放锚点
const pendingAnchor = ref<ZoomAnchor | null>(null)

// 是否指针悬停在 PDF 区域
const isPointerOverPdf = ref(false)

// 是否正在缩放
const isZooming = ref(false)

// 页面尺寸预加载（用于快速滚动时的占位）
// TODO: 是否可以认为论文每页大小相同？
const pageSizes = ref<Map<number, { width: number; height: number }>>(new Map())

// 已渲染完成的页面集合
// TODO: 渲染完成的难道不应该是连续的吗？记录两端即可
const renderedPages = ref<Set<number>>(new Set())

// // ------------------------- 事件监听与响应式处理 -------------------------
// 缩放防抖处理，确保缩放停止后才进行重渲染
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

// 笔记缓存（用于 Ctrl+点击快速查找）
const notesCache = ref<Note[]>([])
const isLoadingNotes = ref(false)

// ------------------------- 辅助计算函数 -------------------------
// 获取指定页面的缩放后尺寸
function getScaledPageSize(pageNumber: number) {
  // 获取页面大小
  const size = pageSizes.value.get(pageNumber)

  // 若发生错误，默认 A4 尺寸
  if (!size) return { width: 612, height: 792 }

  // 缩放大小
  return {
    width: Math.floor(size.width * pdfStore.scale),
    height: Math.floor(size.height * pdfStore.scale)
  }
}

// 页面是否已渲染
function isPageRendered(pageNumber: number) {
  return renderedPages.value.has(pageNumber)
}

// ------------------------- 缩放锚点与位置恢复逻辑 -------------------------
// 捕获当前的中心锚点，用于缩放后恢复位置
// mousePos: 可选的鼠标位置（相对于视口坐标）
function captureCenterAnchor(mousePos?: { x: number; y: number }): ZoomAnchor | null {
  // 获取滚动容器引用
  const container = containerRef.value
  if (!container || !pageNumbers.value.length) return null

  // 返回该容器相对于视口（viewport）的矩形（DOMRect）
  const rect = container.getBoundingClientRect()
  
  // 目标内容坐标（相对于容器内容左上角）
  // 如果有 mousePos，则是鼠标下面的点，否则是视口中心点
  const targetX = mousePos 
    ? (mousePos.x - rect.left + container.scrollLeft) // 鼠标相对屏幕距离 - 容器相对屏幕距离 + PDF相对容器距离
    : (container.scrollLeft + container.clientWidth / 2)
    
  const targetY = mousePos 
    ? (mousePos.y - rect.top + container.scrollTop) 
    : (container.scrollTop + container.clientHeight / 2)

  let anchor: ZoomAnchor | null = null // 初始化锚点变量

  // 这里的查找逻辑可以优化，但保持简单遍历
  // TODO: 要通过 targetY 查找目前鼠标在一页，应该可以用二分法更快定位
  for (const page of pageNumbers.value) {
    const refs = pageRefs.get(page)
    if (!refs) continue
    
    // 获取页面真实布局位置
    // 注意：如果使用了 mx-auto, offsetLeft 会变化
    const pageTop = refs.container.offsetTop
    const pageLeft = refs.container.offsetLeft
    const height = refs.container.offsetHeight || refs.container.clientHeight
    const width = refs.container.offsetWidth || refs.container.clientWidth
    
    if (!height || !width) continue

    // 宽松判断：只要 targetY 在页面垂直范围内（或者非常接近），
    // 并且我们还没找到 anchor，或者这个页面更“中心”
    // 这里简单使用第一个命中的页面
    if (targetY >= pageTop && targetY <= pageTop + height) {
      anchor = { 
        page, 
        ratioY: (targetY - pageTop) / height,
        ratioX: (targetX - pageLeft) / width, // x 比例可以大于 1 或小于 0，这没关系
        destX: mousePos ? mousePos.x - rect.left : undefined,
        destY: mousePos ? mousePos.y - rect.top : undefined
      }
      break
    }
  }
  
  // 兜底：如果遍历完没找到（比如在页面间隙，或者上方空白），取最近的一个页面
  // TODO: 这里可以改进为取离 targetY 最近的页面的顶部或底部
  if (!anchor && pageNumbers.value.length > 0) {
      const firstPage = pageNumbers.value[0]
      if (firstPage !== undefined) {
        const refs = pageRefs.get(firstPage)
        if (refs) {
            // 默认锚定到第一页顶部
            anchor = { page: firstPage, ratioY: 0, ratioX: 0.5 }
        }
      }
  }

  return anchor
}

// 恢复缩放前的位置锚点
function restoreAnchor(anchor: ZoomAnchor) {
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
  const width = refs.container.offsetWidth || refs.container.clientWidth
  if (!height) return

  // 计算原来那个内容点现在的位置
  const currentContentY = refs.container.offsetTop + anchor.ratioY * height
  const currentContentX = refs.container.offsetLeft + anchor.ratioX * width
  
  let top = 0
  let left = 0
  
  if (anchor.destX !== undefined && anchor.destY !== undefined) {
      // 鼠标缩放恢复模式：让内容点回到屏幕上的 dest 位置
      top = currentContentY - anchor.destY
      left = currentContentX - anchor.destX
  } else {
      // 中心缩放恢复模式：让内容点回到视口中心
      top = currentContentY - container.clientHeight / 2
      left = currentContentX - container.clientWidth / 2
  }

  container.scrollTo({
    top,
    left,
    behavior: 'instant' as ScrollBehavior
  })
}

// ------------------------- 引用处理与资源管理 -------------------------

// 处理页面容器的引用挂载
function handlePageContainerRef(
  pageNumber: number, // 当前页码
  ref: Element | ComponentPublicInstance | null, // Vue 传入的泛型引用
  _refs?: Record<string, Element | ComponentPublicInstance> // 备用的 refs 对象占位
) {
  const el = ref instanceof HTMLElement ? ref : null // 仅当 ref 为原生元素时才使用
  setPageRef(pageNumber, el) // 将合法引用交给内部处理
}

// 缓存页面相关的 DOM 引用
function setPageRef(pageNumber: number, el: HTMLElement | null) {
  if (!el) {
    pageRefs.delete(pageNumber) // 若元素不存在则移除缓存
    return
  }

  const canvas = el.querySelector('canvas') // 查找页面对应的画布
  const textLayer = el.querySelector('.textLayer') // 查找页面对应的文字图层
  const linkLayer = el.querySelector('.linkLayer') // 查找页面对应的链接图层
  const highlightLayer = el.querySelector('.highlightLayer') // 查找页面对应的高亮图层

  if (
    canvas instanceof HTMLCanvasElement &&
    textLayer instanceof HTMLDivElement &&
    linkLayer instanceof HTMLDivElement &&
    highlightLayer instanceof HTMLDivElement
  ) {
    pageRefs.set(pageNumber, {
      container: el, // 存储页面容器
      canvas, // 存储画布引用
      textLayer, // 存储 Text Layer 引用
      linkLayer, // 存储 Link Layer引用
      highlightLayer // 存储高亮层引用
    })
  }
}

// ------------------------- 渲染核心与监听调度 -------------------------
// 核心渲染逻辑：仅渲染可见区域页面，大幅提升长文档性能
const updateVisiblePages = useDebounceFn(() => {
  if (!containerRef.value || !pdfDoc.value) return

  const container = containerRef.value
  const { top: containerTop, bottom: containerBottom } = container.getBoundingClientRect()
  const buffer = 200 // 视口上下预加载缓冲区

  // 再次遍历所有页面，检查哪些在视口内（包含缓冲区）
  // TODO: 可以改进为二分法快速定位，或者每一页如果大小一样可以直接计算，而且由于是顺序的，可以从上次检测的位置开始
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

// 监听当前 PDF 地址的变化
watch(
  () => pdfStore.currentPdfUrl, 
  (url) => {
    // 切换文档时重置UI状态
    showTooltip.value = false
    highlightsAtCurrentPoint.value = []
    currentHighlightIndex.value = 0
    // pdfStore.closeNotePreviewCard() // 关闭笔记预览卡片

    if (url) {
      loadPdf(url) // 地址存在则加载 PDF
      loadNotesCache() // 加载笔记缓存
    } else {
      console.log('No PDF URL provided.') // 调试日志
      cleanup() // 地址清空则重置状态
      notesCache.value = [] // 清空笔记缓存
    }
  },
  { immediate: true }
)

// ------------------------- 缩放、跳转与文本选择监听 -------------------------

// 监听缩放比例变化，动态触发位置恢复
watch(
  () => pdfStore.scale, 
  () => {
    // 如果没有 pendingAnchor（说明不是滚轮触发的缩放，而是按钮触发），则使用中心锚点
    if (!pendingAnchor.value) {
      pendingAnchor.value = captureCenterAnchor()
    }

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

// 监听工具栏触发的页面跳转
let lastUserTriggeredPage = 1
watch(
  () => pdfStore.currentPage,
  (page, oldPage) => {
    // 只有当页码变化且不是由滚动触发时才跳转
    if (page !== oldPage && page !== lastUserTriggeredPage) {
      lastUserTriggeredPage = page
      scrollToPage(page, true) // 使用 instant 滚动
    }
  }
)

// 监听选区清除
watch(
  () => pdfStore.selectedText,
  (newText) => {
    if (!newText) {
      window.getSelection()?.removeAllRanges()
      showTooltip.value = false
    }
  }
)

// -------------------------  Link Layer 渲染 -------------------------
// Link Layer 定义
type LinkOverlayRect = {
  left: number
  top: number
  width: number
  height: number
}

// 外部链接的 HTML 格式
function appendLinkOverlay(container: HTMLElement, rect: LinkOverlayRect, href: string, title?: string) {
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

// 内部链接解析
async function resolveDestination(dest: any): Promise<number | null> {
  if (!pdfDoc.value) return null

  try {
    let destArray = dest

    // 如果目标是 String，需要先解析
    if (typeof dest === 'string') {
      destArray = await pdfDoc.value.getDestination(dest)
    }

    // 确保目标是数组
    if (!destArray || !Array.isArray(destArray)) return null

    // 目标数组的第一个元素是页面引用
    // TODO: 是否可以精确到页面的具体位置？
    const pageRef = destArray[0]
    if (!pageRef) return null

    // 获取页码
    const pageIndex = await pdfDoc.value.getPageIndex(pageRef)

    // 页码从 1 开始
    return pageIndex + 1 

  } catch (err) {
    console.error('Error resolving destination:', err)
    return null
  }
}

// ------------------------- 页面重绘与渲染逻辑 -------------------------

// 渲染页面：绘制 Canvas -> 生成 Text Layer -> 生成 Link Layer 
async function renderPage(pageNumber: number, options?: { preserveContent?: boolean }) {
  const pdf = pdfDoc.value // 当前文档实例
  const refs = pageRefs.get(pageNumber) // 当前页的引用集合
  if (!pdf || !refs) return // 缺失则跳过

  // 防止重复渲染同一页
  if(renderTasks.has(pageNumber)) return

  // 是否需要保留已有内容（选项里设置了且该页已渲染过）
  const preserveContent = !!options?.preserveContent && renderedPages.value.has(pageNumber)

  // 获取页面对象
  const page = await pdf.getPage(pageNumber) 

  // 获取PDF视口（把 PDF 的内部坐标系映射到页面/画布坐标）
  const viewport = page.getViewport({ scale: pdfStore.scale })

  // 准备目标 Canvas
  const targetCanvas = preserveContent ? // 是否保留已有内容
    document.createElement('canvas') : // 如是：新建临时 Canvas 用于保留内容
    refs.canvas // 如不是：直接使用页面的 Canvas
  
  // 获取画布 2D 上下文
  const context = targetCanvas.getContext('2d') 
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

  // Text Layer 和 Link Layer 使用逻辑尺寸
  refs.textLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.textLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.textLayer.style.setProperty('--scale-factor', `${viewport.scale}`)
  refs.textLayer.style.transform = 'scale(1)'
  refs.textLayer.style.transformOrigin = 'top left'
  refs.textLayer.innerHTML = '' // 重绘前清空 Text Layer 
  
  // Link Layer 同样使用逻辑尺寸（复用 renderLinkLayer 内部逻辑，也可以在此显式重置防止闪烁）
  refs.linkLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.linkLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.linkLayer.style.transform = 'scale(1)'
  refs.linkLayer.style.transformOrigin = 'top left'

  // 高亮层尺寸与缩放复位
  refs.highlightLayer.style.width = `${Math.floor(viewport.width)}px`
  refs.highlightLayer.style.height = `${Math.floor(viewport.height)}px`
  refs.highlightLayer.style.transform = 'scale(1)'
  refs.highlightLayer.style.transformOrigin = 'top left'

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
  const textDivs: HTMLElement[] = []
  await renderTextLayer({
    textContentSource: textContent, // 提供文字内容
    container: refs.textLayer, // 指定 Text Layer 容器
    viewport, // 提供视口信息
    textDivs // Capture created divs
  }).promise // 等待 Text Layer 绘制完成

  // 修复：强制调整文字宽度以对齐 PDF 原始内容
  if (textContent && textContent.items && textDivs.length === textContent.items.length) {
    const items = textContent.items as any[]
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      const div = textDivs[i]
      
      // 跳过空内容
      if (!item.str || !item.width || !div) continue

      // item.width 是 PDF 坐标系下的宽度
      // viewport.scale 是当前的缩放倍率
      const targetWidth = item.width * viewport.scale
      
      // 获取当前 DOM 元素的实际渲染尺寸（包括 transform）
      const rect = div.getBoundingClientRect()
      
      // 判断文字方向
      // item.transform [a, b, c, d, e, f]
      // 水平文字通常 b=0, c=0
      // 垂直文字通常 a=0, d=0 (90或270度旋转)
      const transform = item.transform
      const isVertical = transform && Math.abs(transform[0]) < 1e-3 && Math.abs(transform[3]) < 1e-3
      const isHorizontal = !transform || (Math.abs(transform[1]) < 1e-3 && Math.abs(transform[2]) < 1e-3)

      let currentLength = 0
      if (isVertical) {
        currentLength = rect.height
      } else if (isHorizontal) {
        currentLength = rect.width
      } else {
        // 对于非正交旋转的文字，跳过宽度调整以避免破坏
        continue 
      }
      
      if (currentLength > 0) {
        // 计算需要的水平缩放比例
        const scaleFactor = targetWidth / currentLength
        
        // 只有当偏差超过一定阈值才调整
        if (Math.abs(scaleFactor - 1) > 0.01) {
            const existingTransform = div.style.transform || ''
            // 追加 scaling，保留原有的旋转和平移
            div.style.transform = `${existingTransform} scaleX(${scaleFactor})`
        }
      }
    }
  }

  try {
    const annotations = await page.getAnnotations()
    renderLinkLayer(annotations, viewport, refs.linkLayer)
  } catch (err) {
    console.error('Error rendering Link Layer :', err)
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

// 渲染 Link Layer 
async function renderLinkLayer(annotations: any[], viewport: any, container: HTMLElement) {
  container.innerHTML = '' // 清空 Link Layer 
  container.style.width = `${viewport.width}px` // 设置宽度
  container.style.height = `${viewport.height}px` // 设置高度

  // 遍历所有PDF注释，找到是链接的注释
  for (const annotation of annotations) {
    if (annotation.subtype !== 'Link') continue

    // 计算注释在视口中的位置
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
}

// ------------------------- PDF 文档加载与预加载策略 -------------------------
// 加载 PDF 文档并初始化尺寸信息与页码列表
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

// ------------------------- 交互处理 (滚动、缩放、点击) -------------------------
// 缩放手势进行时，先按目标尺寸拉伸已有渲染
// TODO: 目前 textlayer 缩放还是不对
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

// 鼠标进入 PDF 框
function handleMouseEnterContainer() {
  isPointerOverPdf.value = true
}

// 鼠标离开 PDF 框
function handleMouseLeaveContainer() {
  isPointerOverPdf.value = false
}

// 水平划动 + 缩放 PDF
// 滚动滚轮或触摸板动作进行时一直触发，负责实时渲染PDF
function handleWheel(event: WheelEvent) {
  // 确保鼠标在 PDF 容器内
  if (!isPointerOverPdf.value) return

  // 获取滚动容器引用
  const container = containerRef.value
  if (!container) return

  // 缩放 PDF：Ctrl + 滚轮（即触摸板双指缩放）
  if (event.ctrlKey) {
    event.preventDefault()
    event.stopPropagation()

    // 是否已经缩放进PDF内了（即PDF是否横向溢出）
    // True 为已经缩放到PDF内，会根据鼠标位置进行定点缩放
    // False 为未缩放到PDF内，统一往中间缩放
    const isHorizontalOverflow = container.scrollWidth > container.clientWidth + 1 // +1 容错

    if (isHorizontalOverflow) {
      // 往鼠标方向放大
      pendingAnchor.value = captureCenterAnchor({ x: event.clientX, y: event.clientY })
    } else {
      // 往中间放大
      pendingAnchor.value = captureCenterAnchor()
    }
    // 算出缩放锚点后，见后面的 watch 监听 pdfStore.scale 变化进行缩放处理

    // 读取缩放大小（由于是ctrl+滚轮，所以不是上下左右滚动，而是缩放手势）
    const delta = event.deltaY

    // 根据滚动距离计算缩放步长（控制缩放速度）
    // TODO: 可以加快放缩速度
    const step = Math.min(0.25, Math.max(0.05, Math.abs(delta) / 500))

    // 计算新的缩放比例
    const nextScale = delta < 0
      ? pdfStore.scale + step // 放大
      : pdfStore.scale - step // 缩小

    // 应用新的缩放比例
    pdfStore.setScale(nextScale)
    return
  }

  // 水平划动 PDF 处理模块
  // 由于垂直划动是浏览器的默认行为，不需要处理
  // 这里主要的作用是阻止浏览器做前进后退的默认行为

  // 水平划动的距离（+为右，-为左）
  const deltaX = event.deltaX

  // 检查水平滚动幅度是否大于垂直滚动的0.5倍。如果是，则判定为主要水平滚动手势（而非垂直滚动）。
  if (Math.abs(deltaX) > Math.abs(event.deltaY) * 0.5) {

    // 当前水平滚动位置
    const scrollLeft = container.scrollLeft

    // 计算水平滚动空间（总宽度 - 可见宽度）
    const maxScrollLeft = container.scrollWidth - container.clientWidth

    // 是否能继续向右或向左滚动
    const canScrollRight = scrollLeft < maxScrollLeft - 1
    const canScrollLeft = scrollLeft > 1

    // 如果能滚动且有水平滚动
    if ((deltaX > 0 && canScrollRight) || (deltaX < 0 && canScrollLeft)) {
      container.scrollLeft += deltaX // 执行水平滚动
      event.preventDefault() // 阻止默认行为（防止前进后退）
    }
    // 否则让浏览器处理（可能是到达边界后的前进后退）
  }
}

// 划动 PDF
// 在滚动容器滚动后触发，负责更新当前页码显示
const handleScroll = useDebounceFn(() => { // useDebounceFn 是防抖函数，只有连续运行一段时间才会执行
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

// ------------------------- 点击与选择处理 -------------------------
// 鼠标点击
function handleMouseDown(event: MouseEvent) {
  // 记录鼠标按下位置和时间
  mouseDownInfo.value = {
    x: event.clientX,
    y: event.clientY,
    time: Date.now()
  }
}

// 鼠标抬起（此时处理是点击还是拖动）
function handleMouseUp(event: MouseEvent) {
  const downInfo = mouseDownInfo.value
  mouseDownInfo.value = null

  // 如果时间超过阈值则判定为拖动
  const isDrag = !!downInfo && (Date.now() - downInfo.time >= CLICK_TIME_THRESHOLD)

  if (isDrag) {
    // 判定为拖动：全部当作文本选择处理
    handleTextSelection()
    return
  }

  // 非拖动（短按）：若点击的是链接，则让浏览器/链接自身处理（不再拦截）
  const target = event.target as HTMLElement
  if (target.tagName === 'A' || target.closest('a') || target.classList.contains('internal-link') || target.closest('.internal-link')) {
    // 点击在链接上，保持默认行为
    return
  }

  // 非拖动且非链接：视作点击并交给常规点击处理逻辑（包括 Ctrl+点击查找笔记等）
  handleClick(event)
}

// 处理普通点击事件
function handleClick(event: MouseEvent) {
  // Ctrl+点击：查找笔记
  if (event.ctrlKey || event.metaKey) {
    handleCtrlClick(event)
    return
  }

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

// ------------------------- 高亮与文本选择处理 -------------------------

// 手动文本选择的处理逻辑（逐行中文注释）
function handleTextSelection() {
  console.log('Handling text selection...')
  const selection = window.getSelection() // 获取当前窗口选择
  
  // 如果没有选择或仅包含空白字符，直接退出
  // TODO: 是否支持划空白？
  if (!selection || !selection.toString().trim()) {
    console.warn('No valid text selected.')
    return
  }
  // 清除任何已有的高亮选择状态（优先处理文本选择）
  pdfStore.clearHighlightSelection()

  // 获取选中的纯文本（去除首尾空白）
  const text = selection.toString().trim()
  // 获取选区的第一个 Range（代表一段连续的文本范围）
  const range = selection.getRangeAt(0)
  // 从 Range 的 commonAncestorContainer 向上查找所属的页面元素（.pdf-page）
  const pageEl = findPageElement(range.commonAncestorContainer)

  // 如果无法定位到页面元素或该元素没有 page 数据属性，则放弃处理
  if (!pageEl || !pageEl.dataset.page) {
    console.warn('Cannot find page element for selected text.')
    return
  }

  // 解析页面的页码（dataset 存储的是字符串）
  // TODO: 以后要支持跨页的高亮
  const pageNumber = Number(pageEl.dataset.page)
  // 找到当前页面上的文本层（textLayer），用于计算坐标和尺寸
  const textLayer = pageEl.querySelector('.textLayer') as HTMLDivElement | null
  console.log('Selected text on page', pageNumber, ':', text)
  if (!textLayer) return

  // 获取文本层在视口中的边界（DOMRect），用于坐标归一化
  const layerRect = textLayer.getBoundingClientRect()
  // 若宽或高为 0（不可见或未渲染），则退出
  if (!layerRect.width || !layerRect.height) return

  // 将选区的每个 ClientRect 转换为相对于 textLayer 的百分比坐标与尺寸
  const rects = Array.from(range.getClientRects())
    .map((rect) => ({
      // left/top/width/height 都改为相对比例（相对于 textLayer 的宽高）
      left: (rect.left - layerRect.left) / layerRect.width,
      top: (rect.top - layerRect.top) / layerRect.height,
      width: rect.width / layerRect.width,
      height: rect.height / layerRect.height,
    }))
    // 过滤掉无效的矩形（宽或高为 0 的情况）
    .filter((rect) => rect.width > 0 && rect.height > 0)

  // 如果没有有效的矩形（例如只包含不可见字符），则退出
  if (!rects.length) return

  // 去重处理：仅移除完全相同的重复矩形，避免把相邻行误判为重复
  const seen = new Set<string>()
  const dedupedRects: typeof rects = []
  rects.forEach((rect) => {
    // 构造用于比较的 key，使用 toFixed 保持小数位一致以便稳定比较
    const key = `${rect.left.toFixed(5)}|${rect.top.toFixed(5)}|${rect.width.toFixed(5)}|${rect.height.toFixed(5)}`
    if (seen.has(key)) return // 已存在则跳过
    seen.add(key) // 标记已见
    dedupedRects.push(rect) // 将不重复的矩形加入最终数组
  })

  // 获取选区的边界矩形（用于在屏幕上定位工具提示的位置）
  const selectionRect = range.getBoundingClientRect() // 选区位置矩形

  // 将选中的文本与提示位置保存到 store，提示位置为选区中心 x 以及稍高于选区顶部的 y
  pdfStore.setSelectedText(text, {
    x: selectionRect.left + selectionRect.width / 2,
    y: selectionRect.top - 10
  })
  // 保存选区信息（所在页和去重后的矩形数组）到 store
  pdfStore.setSelectionInfo({ page: pageNumber, rects: dedupedRects })

  // 同步本地 tooltip 的位置状态（用于组件内显示）
  tooltipPosition.value = {
    x: selectionRect.left + selectionRect.width / 2,
    y: selectionRect.top - 10
  }
  // 打开提示菜单（例如显示高亮/注释等操作）
  showTooltip.value = true // 打开提示
}

function handleClickOutside() {
  const selection = window.getSelection()
  // Keep the action menu open when there is still a text selection
  if (selection && selection.toString().trim()) return

  showTooltip.value = false // 隐藏提示
  pdfStore.clearSelection() // 清空选中文本
  pdfStore.clearHighlightSelection() // 清空高亮选择
  pdfStore.closeNotePreviewCard() // 关闭笔记预览卡片
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

// ------------------------- 笔记缓存与快捷查找 (Ctrl+点击) -------------------------
// 加载当前文档的笔记缓存
async function loadNotesCache() {
  const docId = libraryStore.currentDocument?.id
  if (!docId) {
    notesCache.value = []
    return
  }

  isLoadingNotes.value = true
  try {
    const response = await notesApi.getNotes(docId)
    notesCache.value = response.notes || []
  } catch (error) {
    console.error('Failed to load notes for cache:', error)
    notesCache.value = []
  } finally {
    isLoadingNotes.value = false
  }
}

// 获取点击位置的单词
function getWordAtPoint(x: number, y: number): string | null {
  // 使用 document.caretPositionFromPoint 或 caretRangeFromPoint 获取点击位置
  let range: Range | null = null

  // caretRangeFromPoint (Chrome, Safari)
  if (typeof (document as any).caretRangeFromPoint === 'function') {
    range = (document as any).caretRangeFromPoint(x, y)
  }
  // caretPositionFromPoint (Firefox)
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

// 查找匹配的笔记（模糊匹配标题）
function findMatchingNote(word: string): Note | null {
  if (!word || word.length < 2) return null

  const wordLower = word.toLowerCase()

  // 精确匹配优先
  for (const note of notesCache.value) {
    if (note.title && note.title.toLowerCase() === wordLower) {
      return note
    }
  }

  // 标题包含该词
  for (const note of notesCache.value) {
    if (note.title && note.title.toLowerCase().includes(wordLower)) {
      return note
    }
  }

  // 该词包含标题（标题较短时）
  for (const note of notesCache.value) {
    if (note.title && note.title.length >= 2 && wordLower.includes(note.title.toLowerCase())) {
      return note
    }
  }

  return null
}

// 处理 Ctrl+点击（查找笔记）
function handleCtrlClick(event: MouseEvent) {
  // 关闭其他弹出内容
  pdfStore.closeNotePreviewCard()

  const word = getWordAtPoint(event.clientX, event.clientY)
  if (!word) return

  const matchedNote = findMatchingNote(word)
  if (matchedNote) {
    // 计算卡片显示位置
    const cardX = Math.min(event.clientX + 10, window.innerWidth - 340)
    const cardY = Math.min(event.clientY + 10, window.innerHeight - 400)

    pdfStore.openNotePreviewCard(
      {
        id: matchedNote.id,
        title: matchedNote.title,
        content: matchedNote.content
      },
      { x: Math.max(0, cardX), y: Math.max(0, cardY) }
    )
  }
}

// ------------------------- 段落翻译与辅助函数 -------------------------
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
      <div class="space-y-4 flex flex-col items-center w-fit min-w-full mx-auto">
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
          <div class="linkLayer absolute inset-0" :class="{ 'zooming-layer': isZooming }" /> <!--  Link Layer允许点击内部链接 -->
          
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
              <!-- 极简小光标：小矩形指示器 -->
              <div class="marker-icon">
                <span class="marker-chevron">›</span>
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
    
    <!-- 多窗口翻译面板（可拖动，位于最上层） -->
    <TranslationPanelMulti />

    <!-- 笔记预览卡片（Ctrl+点击触发） -->
    <NotePreviewCard />
  </div>
</template>

<style scoped>
.pdf-page {
  border-radius: 0.75rem; /* 单页容器圆角 */
}

.textLayer {
  pointer-events: auto; /* 允许 Text Layer 响应鼠标事件 */
}

.highlightLayer {
  z-index: 4; /* ensure highlight stays above link overlays */
  pointer-events: none;
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
  cursor: text; /*  Text Layer 中文字光标样式 */
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

/* 段落光标样式 - 发光 > 符号 */
.paragraph-marker {
  z-index: 6;
}

.paragraph-marker .marker-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  transition: all 0.2s ease;
  opacity: 0.5;
}

.paragraph-marker .marker-chevron {
  font-size: 16px;
  font-weight: 600;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  color: rgba(100, 140, 200, 0.8);
  line-height: 1;
  transition: all 0.2s ease;
}

.paragraph-marker:hover .marker-icon {
  opacity: 1;
  transform: scale(1.2) translateX(2px);
}

.paragraph-marker:hover .marker-chevron {
  color: rgba(80, 140, 255, 1);
}

/* 夜间模式段落光标 */
:global(.dark) .paragraph-marker .marker-chevron {
  color: rgba(140, 180, 255, 0.7);
}

:global(.dark) .paragraph-marker:hover .marker-chevron {
  color: rgba(160, 200, 255, 0.95);
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
  color: transparent !important;
  mix-blend-mode: normal;
}

:global(.dark .highlight-selected-box) {
  border-color: #cbd5ff;
}

:global(.dark .loading-spinner) {
  border-color: #1f2937;
  border-top-color: #9ca3af;
}

/* Dark mode scrollbar for the PDF scroller */
:global(.dark .pdf-scroll-container::-webkit-scrollbar) {
  width: 10px;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-track) {
  background: #111827;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-thumb) {
  background: #4b5563;
  border-radius: 6px;
}

:global(.dark .pdf-scroll-container::-webkit-scrollbar-thumb:hover) {
  background: #6b7280;
}

/* Fix for PDF text layer alignment and font matching (ICML / Times New Roman) */
:deep(.textLayer) {
  opacity: 1;
}

:deep(.textLayer span) {
  color: transparent !important;
  line-height: 1.0 !important;
  letter-spacing: 0.2px !important;
  transform-origin: 0 0;
  font-family: "Times New Roman", "Nimbus Roman No9 L", "FreeSerif", "Liberation Serif", serif !important;
  white-space: pre;
  cursor: text;
}

:deep(.textLayer ::selection) {
  background: rgba(59, 130, 246, 0.3) !important;
}
</style>
