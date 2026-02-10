<script setup lang="ts">
// =============================================================================
// TranslationPanelMulti.vue
//
// 功能概述：多实例翻译面板管理器，允许在 PDF 页面同时打开和管理多个段落翻译窗口。
// - 每个面板实例存储在 `translationStore.translationPanels` 中（包含 id、position、size、snapMode 等）。
// - 提供拖拽、吸附到段落、停靠到侧边栏、尺寸调整、复制译文、字体缩放、置顶等交互。
// - 为了性能与流畅性，使用防抖（useDebounceFn）、requestAnimationFrame、ResizeObserver 等手段优化滚动与重排的更新。
// 交互要点：
// - 拖动期间会计算与最近段落或侧边栏的距离以决定是否显示吸附提示，并在释放时切换 snapMode。
// - 吸附到段落的面板会在缩放或滚动时重新计算位置/尺寸以精确覆盖原文段落。
// - 目标是让用户可以并行查看多个段落的译文并灵活组织它们的布局。
// =============================================================================
/* 导入：Vue 响应式 API、debounce 工具、pdf store、可复用拖拽/缩放 hook、翻译 composable、类型定义 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { usePdfStore } from '../../stores/pdf'
import { useTranslationStore } from '../../stores/translation'
import { useDraggableWindow } from '../../composables/useDraggableWindow'
import { useResizableWindow } from '../../composables/useResizableWindow'
import type { TranslationPanelInstance } from '../../types'

const pdfStore = usePdfStore()
const translationStore = useTranslationStore()

// 当前拖动的面板
const draggingPanelId = ref<string | null>(null)

// 调整大小相关
const resizingPanelId = ref<string | null>(null)

// 吸附相关
const isNearSnapTarget = ref(false) // 是否接近吸附目标（段落）
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null) // 吸附目标的矩形区域
const snapTargetParagraphId = ref<string | null>(null) // 吸附目标段落的ID
const isNearSidebar = ref(false) // 是否接近侧边栏

// 字体大小管理
const fontSizeMap: Record<string, number> = {} // panelId -> fontSize 映射，存储每个面板的字体大小
const DEFAULT_FONT_SIZE = 14 // 默认字体大小
const MIN_FONT_SIZE = 12 // 最小字体大小
const MAX_FONT_SIZE = 24 // 最大字体大小

// 复制状态
const copiedPanelId = ref<string | null>(null) // 最近复制翻译内容的面板ID，用于显示复制成功状态

// 复制翻译内容到剪贴板（并显示短暂的复制成功提示）
// 说明：复制失败会在控制台记录错误，复制成功会把状态写入 `copiedPanelId`，2s 后自动清除以恢复按钮状态。
async function copyTranslation(panel: TranslationPanelInstance) { // 异步函数，复制指定面板的翻译内容
  if (!panel.translation) return // 如果没有翻译内容，直接返回

  try {
    await navigator.clipboard.writeText(panel.translation) // 将翻译内容写入系统剪贴板
    copiedPanelId.value = panel.id // 设置复制状态为当前面板ID
    // 2秒后重置状态，清除复制成功提示
    setTimeout(() => {
      if (copiedPanelId.value === panel.id) { // 检查是否还是同一个面板，避免多面板同时复制时的冲突
        copiedPanelId.value = null // 重置复制状态
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err) // 复制失败时记录错误信息
  }
}

// 获取指定面板的字体大小
function getFontSize(panelId: string): number { // 返回面板的当前字体大小
  return fontSizeMap[panelId] || DEFAULT_FONT_SIZE // 从映射中获取，或返回默认值
}

// 增加指定面板的字体大小
function increaseFontSize(panelId: string) { // 增大字体
  const current = getFontSize(panelId) // 获取当前字体大小
  if (current < MAX_FONT_SIZE) { // 如果小于最大值
    fontSizeMap[panelId] = current + 1 // 增加1px
  }
}

// 减少指定面板的字体大小
function decreaseFontSize(panelId: string) { // 减小字体
  const current = getFontSize(panelId) // 获取当前字体大小
  if (current > MIN_FONT_SIZE) { // 如果大于最小值
    fontSizeMap[panelId] = current - 1 // 减少1px
  }
}

// 面板尺寸限制常量
const MIN_WIDTH = 280 // 最小面板宽度
const MAX_WIDTH = 900 // 最大面板宽度
const MIN_HEIGHT = 150 // 最小面板高度
const MAX_HEIGHT = 600 // 最大面板高度
const SIDEBAR_SNAP_THRESHOLD = 100 // 侧边栏吸附阈值距离（像素）
const PARAGRAPH_SNAP_THRESHOLD = 150 // 段落吸附阈值距离（像素）

// 获取所有可吸附的段落位置信息
function getAllParagraphRects(): Array<{ id: string; rect: DOMRect; page: number }> { // 返回所有段落的矩形信息数组
  const results: Array<{ id: string; rect: DOMRect; page: number }> = [] // 初始化结果数组
  const markers = document.querySelectorAll('[data-paragraph-id]') // 查找所有带有段落ID属性的元素
  markers.forEach(marker => { // 遍历每个标记元素
    const id = marker.getAttribute('data-paragraph-id') // 获取段落ID
    if (id) { // 如果ID存在
      const pageEl = marker.closest('.pdf-page') // 找到最近的PDF页面元素
      const page = pageEl ? Number(pageEl.getAttribute('data-page')) : 0 // 获取页面号
      results.push({ id, rect: marker.getBoundingClientRect(), page }) // 添加到结果数组
    }
  })
  return results // 返回段落信息数组
}

// 计算指定段落的吸附位置（将段落 bbox 基于 pdfStore.scale 映射到当前渲染坐标）
// 说明：
// - 本函数会查找段落数据并计算其在当前页面与缩放下的屏幕坐标，用于把面板精确放置到原文上方。
// - 采用 pdfStore.scale 作为缩放因子（与 render pipeline 保持一致），并返回包含 pageElement 的位置信息以便后续使用。
function calculateParagraphSnapPosition(paragraphId: string) { // 根据段落ID计算吸附位置
  const paragraphs = pdfStore.paragraphs // 获取所有段落数据
  const paragraph = paragraphs.find(p => p.id === paragraphId) // 查找指定段落
  if (!paragraph) return null // 如果没找到段落，返回null

  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement // 找到段落所在页面元素
  if (!pageElement) return null // 如果页面元素不存在，返回null

  const pageRect = pageElement.getBoundingClientRect() // 获取页面元素的边界矩形

  // 直接使用 pdfStore.scale 作为缩放因子
  const scaleFactor = pdfStore.scale // 获取当前PDF缩放因子

  // bbox坐标是相对于原始PDF尺寸（scale=1）的绝对坐标
  // 需要乘以当前缩放因子得到当前渲染尺寸下的坐标
  // pageRect.left/top 是页面在屏幕上的位置（会随滚动变化）
  const left = pageRect.left + (paragraph.bbox.x0 * scaleFactor) // 计算段落在屏幕上的左边距
  const top = pageRect.top + (paragraph.bbox.y0 * scaleFactor) // 计算段落在屏幕上的上边距
  const width = paragraph.bbox.width * scaleFactor // 计算段落的宽度
  const height = paragraph.bbox.height * scaleFactor // 计算段落的高度

  return { // 返回吸附位置信息
    left,
    top,
    width,
    height,
    pageElement
  }
}

// 拖动处理：用于处理任意面板的拖拽逻辑
// 说明：
// - 在拖动过程中检测是否接近侧边栏或周围段落的吸附目标，并设置相应的提示状态；
// - onDragEnd 会根据是否接近侧边栏或段落决定面板的 snapMode（sidebar / paragraph / none），并在需要时更新位置与尺寸；
// - 拖动过程中也会限制面板位置使其保持在视口范围内并同步回 store。
const { startDrag: initDrag, setPosition: setDragPosition } = useDraggableWindow({
  onDrag: (newPos) => {
    if (!draggingPanelId.value) return
    const panel = translationStore.translationPanels.find(p => p.id === draggingPanelId.value)
    if (!panel) return
    
    // Snapping Logic
    const distanceToRight = window.innerWidth - (newPos.x + panel.size.width)
    isNearSidebar.value = distanceToRight < SIDEBAR_SNAP_THRESHOLD
    
    if (!isNearSidebar.value) {
      const allParagraphs = getAllParagraphRects()
      let nearestParagraph: { id: string; distance: number; rect: DOMRect } | null = null
      
      const panelCenterX = newPos.x + panel.size.width / 2
      const panelCenterY = newPos.y + panel.size.height / 2

      for (const p of allParagraphs) {
        const markerCenterX = p.rect.left + p.rect.width / 2
        const markerCenterY = p.rect.top + p.rect.height / 2
        const distanceFromCorner = Math.sqrt(Math.pow(newPos.x - markerCenterX, 2) + Math.pow(newPos.y - markerCenterY, 2))
        const distanceFromCenter = Math.sqrt(Math.pow(panelCenterX - markerCenterX, 2) + Math.pow(panelCenterY - markerCenterY, 2))
        const distance = Math.min(distanceFromCorner, distanceFromCenter)

        if (distance < PARAGRAPH_SNAP_THRESHOLD) {
          if (!nearestParagraph || distance < nearestParagraph.distance) {
            nearestParagraph = { id: p.id, distance, rect: p.rect }
          }
        }
      }

      if (nearestParagraph) {
        isNearSnapTarget.value = true
        snapTargetParagraphId.value = nearestParagraph.id
        const snapPos = calculateParagraphSnapPosition(nearestParagraph.id)
        if (snapPos) snapTargetRect.value = snapPos
      } else {
        isNearSnapTarget.value = false
        snapTargetParagraphId.value = null
        snapTargetRect.value = null
      }
    } else {
      isNearSnapTarget.value = false
      snapTargetParagraphId.value = null
      snapTargetRect.value = null
    }

    // Constraints
    const maxX = window.innerWidth - panel.size.width
    const maxY = window.innerHeight - panel.size.height
    
    translationStore.updatePanelPosition(draggingPanelId.value, {
      x: Math.max(0, Math.min(maxX, newPos.x)),
      y: Math.max(0, Math.min(maxY, newPos.y))
    })
  },
  onDragEnd: () => {
    if (draggingPanelId.value) {
      const panel = translationStore.translationPanels.find(p => p.id === draggingPanelId.value)
      if (panel) {
        if (isNearSidebar.value) {
          translationStore.setPanelSnapMode(draggingPanelId.value, 'sidebar')
        } else if (isNearSnapTarget.value && snapTargetRect.value && snapTargetParagraphId.value) {
          translationStore.setPanelSnapMode(draggingPanelId.value, 'paragraph', snapTargetParagraphId.value)
          translationStore.updatePanelPosition(draggingPanelId.value, {
            x: snapTargetRect.value.left,
            y: snapTargetRect.value.top
          })
          translationStore.updatePanelSize(draggingPanelId.value, {
            width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, snapTargetRect.value.width)),
            height: panel.size.height
          })
        }
      }
    }
    draggingPanelId.value = null
    isNearSnapTarget.value = false
    isNearSidebar.value = false
    snapTargetRect.value = null
    snapTargetParagraphId.value = null
  }
})

function startDrag(e: MouseEvent, panelId: string) {
  if (!(e.target as HTMLElement).closest('.panel-header')) return
  
  const panel = translationStore.translationPanels.find(p => p.id === panelId)
  if (!panel) return
  
  draggingPanelId.value = panelId
  setDragPosition(panel.position)
  
  translationStore.setPanelSnapMode(panelId, 'none')
  translationStore.bringPanelToFront(panelId)
  
  initDrag(e)
}

// 调整大小处理
const { startResize: initResize, setSize: setResizeSize } = useResizableWindow({
  minWidth: MIN_WIDTH, maxWidth: MAX_WIDTH, minHeight: MIN_HEIGHT, maxHeight: MAX_HEIGHT,
  onResize: ({ size, delta }) => {
    if (!resizingPanelId.value) return
    const panel = translationStore.translationPanels.find(p => p.id === resizingPanelId.value)
    if (!panel) return

    translationStore.updatePanelSize(resizingPanelId.value, size)
    
    if (delta.x !== 0 || delta.y !== 0) {
      translationStore.updatePanelPosition(resizingPanelId.value, {
        x: panel.position.x + delta.x,
        y: panel.position.y + delta.y
      })
    }
  },
  onResizeEnd: () => {
    resizingPanelId.value = null
  }
})

function startResize(e: MouseEvent, panelId: string, direction: string) {
  const panel = translationStore.translationPanels.find(p => p.id === panelId)
  if (!panel) return
  
  resizingPanelId.value = panelId
  setResizeSize(panel.size)
  translationStore.bringPanelToFront(panelId)
  
  initResize(e, direction)
}

// 关闭指定面板
function closePanel(panelId: string) { // 关闭翻译面板
  translationStore.closeTranslationPanelById(panelId) // 调用store关闭面板
}

// 重新翻译指定面板的内容
async function retranslate(panel: TranslationPanelInstance) {
  if (!panel.paragraphId) return
  
  translationStore.setPanelLoading(panel.id, true)
  
  const translation = await translationStore.translateParagraph(panel.paragraphId, true)
  if (translation) {
    translationStore.setTranslation(panel.paragraphId, translation)
  }
}

// 获取指定面板的翻译内容（向后端请求并把结果写回 store，处理加载状态与错误提示）
async function fetchTranslation(panel: TranslationPanelInstance) {
  if (!panel.paragraphId || panel.translation) return
  
  // 标记该面板为加载中（UI 将显示 loading 状态）
  translationStore.setPanelLoading(panel.id, true)
  
  // 调用翻译 composable 请求翻译结果
  const translation = await translationStore.translateParagraph(panel.paragraphId)
  if (translation) {
    // 成功则将翻译结果写入 store（store 会把结果分配到相关 panel）
    translationStore.setTranslation(panel.paragraphId, translation)
  } else {
    // 失败则写入错误提示，前端可在 UI 中显示
    translationStore.setTranslation(panel.paragraphId, '翻译失败，请重试')
  }
}

// 监听面板数量变化，自动请求翻译
watch(() => translationStore.translationPanels.length, () => { // 监听翻译面板数组长度变化
  translationStore.translationPanels.forEach(panel => { // 遍历所有面板
    if (!panel.translation && panel.isLoading) { // 如果面板没有翻译内容且正在加载
      fetchTranslation(panel) // 获取翻译
    }
  })
}, { immediate: true }) // 立即执行一次

// 监听PDF缩放变化，更新吸附面板位置
watch(() => pdfStore.scale, () => { // 监听PDF缩放因子变化
  // 延迟执行以等待DOM更新
  setTimeout(() => {
    debouncedUpdatePositions() // 防抖更新位置
  }, 100)
})

// 更新所有吸附到段落的面板位置
function updateSnappedPanelPositions() { // 更新所有吸附面板的位置
  translationStore.translationPanels.forEach(panel => { // 遍历所有面板
    if (panel.snapMode === 'paragraph' && panel.snapTargetParagraphId) { // 如果面板吸附到段落
      const snapPos = calculateParagraphSnapPosition(panel.snapTargetParagraphId) // 计算吸附位置
      if (snapPos) { // 如果位置计算成功
        translationStore.updatePanelPosition(panel.id, { // 更新面板位置
          x: snapPos.left,
          y: snapPos.top
        })
        // 同时更新宽度以匹配段落
        translationStore.updatePanelSize(panel.id, { // 更新面板尺寸
          width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, snapPos.width)), // 限制宽度
          height: panel.size.height // 保持高度
        })
      }
    }
  })
}

// 防抖的位置更新函数，减少频繁更新
const debouncedUpdatePositions = useDebounceFn(updateSnappedPanelPositions, 16) // 16ms防抖

// 使用 requestAnimationFrame 实现平滑滚动跟随
let scrollRafId: number | null = null // RAF请求ID

function onPdfScroll() { // PDF滚动事件处理
  // 取消之前的 RAF 请求
  if (scrollRafId) { // 如果有之前的RAF请求
    cancelAnimationFrame(scrollRafId) // 取消它
  }
  // 使用 RAF 确保流畅更新
  scrollRafId = requestAnimationFrame(() => { // 请求动画帧
    updateSnappedPanelPositions() // 更新吸附面板位置
    scrollRafId = null // 重置ID
  })
}

// 点击面板时聚焦
function focusPanel(panelId: string) { // 将指定面板置于顶层
  translationStore.bringPanelToFront(panelId) // 调用store置于顶层
}

// 存储事件监听器引用
let pdfContainerRef: Element | null = null // PDF容器元素引用
let resizeObserver: ResizeObserver | null = null // 调整大小观察器引用

// 绑定滚动监听器（带重试机制）
// 说明：
// - 在某些 PDF 渲染实现中，滚动容器可能延迟渲染或切换，故使用重试机制以保证能正确绑定。
// - 绑定后会监听 scroll（被动监听）并使用 ResizeObserver 监听容器尺寸变化，结合防抖与 RAF 优化吸附面板的更新，减少卡顿。
let bindRetryCount = 0 // 绑定重试计数
const MAX_BIND_RETRIES = 10 // 最大重试次数

function bindScrollListener() { // 绑定PDF滚动监听器
  if (pdfContainerRef) return // 如果已经绑定，返回

  pdfContainerRef = document.querySelector('.pdf-scroll-container') // 查找PDF滚动容器
  if (pdfContainerRef) { // 如果找到容器
    pdfContainerRef.addEventListener('scroll', onPdfScroll, { passive: true }) // 添加滚动监听器

    // 监听容器大小变化
    resizeObserver = new ResizeObserver(() => { // 创建大小观察器
      debouncedUpdatePositions() // 更新位置
    })
    resizeObserver.observe(pdfContainerRef) // 观察容器大小变化
    bindRetryCount = 0 // 重置重试计数
  } else if (bindRetryCount < MAX_BIND_RETRIES) { // 如果没找到且未超过重试次数
    // 容器未找到，延迟重试
    bindRetryCount++ // 增加重试计数
    setTimeout(bindScrollListener, 200) // 200ms后重试
  }
}

// 监听 PDF URL 变化，重新绑定监听器
watch(() => pdfStore.currentPdfUrl, () => { // 监听当前PDF URL变化
  // 先解绑旧的监听器
  if (pdfContainerRef) { // 如果有容器引用
    pdfContainerRef.removeEventListener('scroll', onPdfScroll) // 移除滚动监听器
    if (resizeObserver) { // 如果有观察器
      resizeObserver.disconnect() // 断开观察器
      resizeObserver = null // 重置引用
    }
    pdfContainerRef = null // 重置容器引用
  }
  bindRetryCount = 0 // 重置重试计数
  // PDF 切换时重新绑定
  setTimeout(bindScrollListener, 200) // 延迟绑定
}, { immediate: true }) // 立即执行一次

onMounted(() => {
  // 延迟绑定，确保 PDF 容器已渲染
  setTimeout(bindScrollListener, 200)
})

onBeforeUnmount(() => {
  if (pdfContainerRef) {
    pdfContainerRef.removeEventListener('scroll', onPdfScroll) // 移除滚动监听
    pdfContainerRef = null // 重置引用
  }

  if (resizeObserver) { // 如果有观察器
    resizeObserver.disconnect() // 断开观察器
    resizeObserver = null // 重置引用
  }

  if (scrollRafId) { // 如果有RAF请求
    cancelAnimationFrame(scrollRafId) // 取消请求
    scrollRafId = null // 重置ID
  }
})
</script>

<template>
  <!-- 拖动时显示的吸附提示 -->
  <div
    v-if="draggingPanelId && snapTargetRect && isNearSnapTarget"
    class="snap-hint fixed z-[998] pointer-events-none"
    :style="{
      left: snapTargetRect.left + 'px',
      top: snapTargetRect.top + 'px',
      width: snapTargetRect.width + 'px',
      height: snapTargetRect.height + 'px',
    }"
  >
    <div class="snap-hint-text">释放以吸附</div>
  </div>
  
  <!-- 侧边栏吸附提示 -->
  <div
    v-if="draggingPanelId && isNearSidebar"
    class="sidebar-snap-hint fixed z-[998] pointer-events-none right-0 top-0 bottom-0 w-16"
  >
    <div class="sidebar-hint-text">停靠到侧边栏</div>
  </div>

  <!-- 渲染所有翻译面板（排除已停靠到侧边栏的） -->
  <template v-for="(panel, index) in translationStore.translationPanels.filter(p => !p.isSidebarDocked)" :key="panel.id">
    <div
      class="translation-panel fixed z-[1000] rounded-lg overflow-hidden select-none"
      :class="{ 
        'is-snapped': panel.snapMode === 'paragraph',
        'is-dragging': draggingPanelId === panel.id
      }"
      :style="{
        left: panel.position.x + 'px',
        top: panel.position.y + 'px',
        width: panel.size.width + 'px',
        height: panel.size.height + 'px',
        zIndex: 1000 + index
      }"
      @mousedown="focusPanel(panel.id)"
    >
      <!-- 头部 - 极简细条拖动区域 -->
      <div 
        class="panel-header flex items-center justify-between px-2 py-1 cursor-move"
        @mousedown="startDrag($event, panel.id)"
      >
        <div class="flex items-center gap-1.5">
          <span class="text-xs font-medium text-gray-600 dark:text-gray-400">译文</span>
          <span v-if="panel.snapMode === 'paragraph'" class="text-[10px] text-gray-400 dark:text-gray-500">· 已吸附</span>
        </div>
        <div class="flex items-center gap-0.5">
          <!-- 复制按钮 -->
          <button
            @click.stop="copyTranslation(panel)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            :title="copiedPanelId === panel.id ? '已复制' : '复制译文'"
            :disabled="panel.isLoading || !panel.translation"
          >
            <svg v-if="copiedPanelId === panel.id" class="w-3 h-3 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <svg v-else class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
          <!-- 字体减小按钮 -->
          <button
            @click.stop="decreaseFontSize(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="减小字体"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
            </svg>
          </button>
          <!-- 字体增大按钮 -->
          <button
            @click.stop="increaseFontSize(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="增大字体"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <!-- 重新翻译按钮 -->
          <button
            @click.stop="retranslate(panel)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="重新翻译"
            :disabled="panel.isLoading"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" :class="{ 'animate-spin': panel.isLoading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <!-- 关闭按钮 -->
          <button
            @click.stop="closePanel(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="关闭"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      
      <!-- 内容区域 -->
      <div class="panel-content flex-1 overflow-y-auto p-3 cursor-auto select-text" @mousedown.stop>
        <!-- 加载中状态 -->
        <div v-if="panel.isLoading" class="flex flex-col items-center justify-center py-6">
          <div class="loading-spinner mb-2"></div>
          <span class="text-gray-400 dark:text-gray-500 text-xs">翻译中...</span>
        </div>

        <!-- 翻译内容 -->
        <div
          v-else
          class="translation-text text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap"
          :style="{ fontSize: getFontSize(panel.id) + 'px' }"
        >
          {{ panel.translation || '暂无翻译' }}
        </div>
      </div>
      
      <!-- 调整大小的边框（非侧边栏模式） -->
      <template v-if="!panel.isSidebarDocked">
        <div class="resize-handle resize-w" @mousedown="startResize($event, panel.id, 'w')"></div>
        <div class="resize-handle resize-e" @mousedown="startResize($event, panel.id, 'e')"></div>
        <div class="resize-handle resize-s" @mousedown="startResize($event, panel.id, 's')"></div>
        <div class="resize-handle resize-sw" @mousedown="startResize($event, panel.id, 'sw')"></div>
        <div class="resize-handle resize-se" @mousedown="startResize($event, panel.id, 'se')"></div>
      </template>
    </div>
  </template>
</template>

<style scoped>
.translation-panel {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* 夜间模式 - 与Chat面板保持一致的深色背景 */
.dark .translation-panel {
  background: #1e1e1e; /* 与Chat一致的深色背景 */
  border-color: #121726;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* 极简顶栏 - 低饱和度云雾般的灰蓝 */
.panel-header {
  height: 24px;
  background: linear-gradient(to right, #e8eef3, #dfe6ed);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

/* 夜间模式顶栏 - 与sidebar风格一致 */
.dark .panel-header {
  background: #252526;
  border-bottom-color: #121726;
}

.translation-panel.is-snapped {
  border: 1px solid rgba(120, 140, 160, 0.3);
}

.dark .translation-panel.is-snapped {
  border-color: rgba(140, 160, 180, 0.2);
}

.translation-panel.is-sidebar-docked {
  border-radius: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.1);
}

.dark .translation-panel.is-sidebar-docked {
  border-left-color: rgba(255, 255, 255, 0.08);
}

.translation-panel.is-dragging {
  opacity: 0.9;
  cursor: grabbing;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #9ca3af;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.dark .loading-spinner {
  border-color: #374151;
  border-top-color: #6b7280;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 滚动条 */
.panel-content::-webkit-scrollbar {
  width: 4px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}

.panel-content::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

.dark .panel-content::-webkit-scrollbar-thumb {
  background: #4b5563;
}

.dark .panel-content::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}

/* 调整大小边框 */
.resize-handle {
  position: absolute;
  background: transparent;
}

.resize-w {
  left: 0;
  top: 24px;
  bottom: 6px;
  width: 4px;
  cursor: ew-resize;
}

.resize-e {
  right: 0;
  top: 24px;
  bottom: 6px;
  width: 4px;
  cursor: ew-resize;
}

.resize-s {
  bottom: 0;
  left: 6px;
  right: 6px;
  height: 4px;
  cursor: ns-resize;
}

.resize-sw {
  left: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  cursor: nesw-resize;
}

.resize-se {
  right: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  cursor: nwse-resize;
}

.resize-handle:hover {
  background: rgba(120, 140, 160, 0.1);
}

/* 吸附提示框 */
.snap-hint {
  border: 2px dashed rgba(59, 130, 246, 0.6);
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.1);
  transition: all 0.15s ease;
  animation: snap-pulse 1s ease-in-out infinite;
}

@keyframes snap-pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}

.snap-hint-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

/* 侧边栏吸附提示 */
.sidebar-snap-hint {
  background: linear-gradient(to left, rgba(59, 130, 246, 0.15), transparent);
  border-left: 2px dashed rgba(59, 130, 246, 0.5);
}

.sidebar-hint-text {
  position: absolute;
  top: 50%;
  right: 16px;
  transform: translateY(-50%) rotate(-90deg);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
</style>
