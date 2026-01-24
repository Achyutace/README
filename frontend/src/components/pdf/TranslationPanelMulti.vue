<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { aiApi } from '../../api'
import { useLibraryStore } from '../../stores/library'
import type { TranslationPanelInstance } from '../../types'

const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

// 当前拖动的面板
const draggingPanelId = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

// 调整大小相关
const resizingPanelId = ref<string | null>(null)
const resizeDirection = ref<string>('')
const resizeStart = ref({ x: 0, y: 0, width: 0, height: 0 })

// 吸附相关
const isNearSnapTarget = ref(false)
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null)
const snapTargetParagraphId = ref<string | null>(null)
const isNearSidebar = ref(false)

// 字体大小管理
const fontSizeMap: Record<string, number> = {} // panelId -> fontSize
const DEFAULT_FONT_SIZE = 14
const MIN_FONT_SIZE = 12
const MAX_FONT_SIZE = 24

function getFontSize(panelId: string): number {
  return fontSizeMap[panelId] || DEFAULT_FONT_SIZE
}

function increaseFontSize(panelId: string) {
  const current = getFontSize(panelId)
  if (current < MAX_FONT_SIZE) {
    fontSizeMap[panelId] = current + 1
  }
}

function decreaseFontSize(panelId: string) {
  const current = getFontSize(panelId)
  if (current > MIN_FONT_SIZE) {
    fontSizeMap[panelId] = current - 1
  }
}

// 面板尺寸限制
const MIN_WIDTH = 280
const MAX_WIDTH = 900
const MIN_HEIGHT = 150
const MAX_HEIGHT = 600
const SIDEBAR_SNAP_THRESHOLD = 80
const PARAGRAPH_SNAP_THRESHOLD = 100

// 获取所有可吸附的段落位置
function getAllParagraphRects(): Array<{ id: string; rect: DOMRect; page: number }> {
  const results: Array<{ id: string; rect: DOMRect; page: number }> = []
  const markers = document.querySelectorAll('[data-paragraph-id]')
  markers.forEach(marker => {
    const id = marker.getAttribute('data-paragraph-id')
    if (id) {
      const pageEl = marker.closest('.pdf-page')
      const page = pageEl ? Number(pageEl.getAttribute('data-page')) : 0
      results.push({ id, rect: marker.getBoundingClientRect(), page })
    }
  })
  return results
}

// 计算指定段落的吸附位置 - 精准覆盖原文
function calculateParagraphSnapPosition(paragraphId: string) {
  const paragraphs = pdfStore.paragraphs
  const paragraph = paragraphs.find(p => p.id === paragraphId)
  if (!paragraph) return null
  
  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement
  if (!pageElement) return null
  
  const pageRect = pageElement.getBoundingClientRect()
  
  // 直接使用pageElement的尺寸和bbox的百分比计算
  // bbox的坐标是相对于原始PDF页面尺寸的绝对值
  // 我们需要根据当前渲染尺寸进行缩放
  const pageWidth = pageElement.offsetWidth
  const pageHeight = pageElement.offsetHeight
  
  // 获取原始PDF页面尺寸（从canvas获取）
  const canvas = pageElement.querySelector('canvas')
  if (!canvas) return null
  
  // canvas的width/height是像素尺寸（包含devicePixelRatio），需要除以dpr得到CSS尺寸
  const dpr = window.devicePixelRatio || 1
  const originalWidth = canvas.width / dpr
  const originalHeight = canvas.height / dpr
  
  // 计算缩放比例
  const scaleX = pageWidth / originalWidth
  const scaleY = pageHeight / originalHeight
  
  // 计算精确的吸附位置
  const left = pageRect.left + (paragraph.bbox.x0 * scaleX)
  const top = pageRect.top + (paragraph.bbox.y0 * scaleY)
  const width = paragraph.bbox.width * scaleX
  const height = paragraph.bbox.height * scaleY
  
  return {
    left,
    top,
    width,
    height,
    pageElement
  }
}

// 开始拖动
function startDrag(e: MouseEvent, panelId: string) {
  if (!(e.target as HTMLElement).closest('.panel-header')) return
  
  const panel = pdfStore.translationPanels.find(p => p.id === panelId)
  if (!panel) return
  
  draggingPanelId.value = panelId
  dragOffset.value = {
    x: e.clientX - panel.position.x,
    y: e.clientY - panel.position.y
  }
  
  // 取消吸附状态
  pdfStore.setPanelSnapMode(panelId, 'none')
  pdfStore.bringPanelToFront(panelId)
  
  e.preventDefault()
}

// 拖动中
function onDrag(e: MouseEvent) {
  if (resizingPanelId.value) {
    onResize(e)
    return
  }
  
  if (!draggingPanelId.value) return
  
  const panel = pdfStore.translationPanels.find(p => p.id === draggingPanelId.value)
  if (!panel) return
  
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  
  // 检测是否接近右边缘（侧边栏吸附）
  const distanceToRight = window.innerWidth - (newX + panel.size.width)
  isNearSidebar.value = distanceToRight < SIDEBAR_SNAP_THRESHOLD
  
  // 检测是否接近任何段落（段落吸附）
  if (!isNearSidebar.value) {
    const allParagraphs = getAllParagraphRects()
    let nearestParagraph: { id: string; distance: number; rect: DOMRect } | null = null
    
    for (const p of allParagraphs) {
      const centerX = p.rect.left + p.rect.width / 2
      const centerY = p.rect.top + p.rect.height / 2
      const distance = Math.sqrt(Math.pow(newX - centerX, 2) + Math.pow(newY - centerY, 2))
      
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
      if (snapPos) {
        snapTargetRect.value = snapPos
      }
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
  
  // 限制在视口内
  const maxX = window.innerWidth - panel.size.width
  const maxY = window.innerHeight - panel.size.height
  
  pdfStore.updatePanelPosition(draggingPanelId.value, {
    x: Math.max(0, Math.min(maxX, newX)),
    y: Math.max(0, Math.min(maxY, newY))
  })
}

// 停止拖动
function stopDrag() {
  if (draggingPanelId.value) {
    const panel = pdfStore.translationPanels.find(p => p.id === draggingPanelId.value)
    
    if (panel) {
      if (isNearSidebar.value) {
        // 吸附到侧边栏
        pdfStore.setPanelSnapMode(draggingPanelId.value, 'sidebar')
      } else if (isNearSnapTarget.value && snapTargetRect.value && snapTargetParagraphId.value) {
        // 吸附到段落 - 精确覆盖原文位置
        pdfStore.setPanelSnapMode(draggingPanelId.value, 'paragraph', snapTargetParagraphId.value)
        pdfStore.updatePanelPosition(draggingPanelId.value, {
          x: snapTargetRect.value.left,
          y: snapTargetRect.value.top
        })
        // 调整宽度匹配段落
        pdfStore.updatePanelSize(draggingPanelId.value, {
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
  resizingPanelId.value = null
  resizeDirection.value = ''
}

// 开始调整大小
function startResize(e: MouseEvent, panelId: string, direction: string) {
  e.stopPropagation()
  e.preventDefault()
  
  const panel = pdfStore.translationPanels.find(p => p.id === panelId)
  if (!panel) return
  
  resizingPanelId.value = panelId
  resizeDirection.value = direction
  resizeStart.value = {
    x: e.clientX,
    y: e.clientY,
    width: panel.size.width,
    height: panel.size.height
  }
  
  pdfStore.bringPanelToFront(panelId)
}

// 调整大小中
function onResize(e: MouseEvent) {
  if (!resizingPanelId.value) return
  
  const panel = pdfStore.translationPanels.find(p => p.id === resizingPanelId.value)
  if (!panel) return
  
  const deltaX = e.clientX - resizeStart.value.x
  const deltaY = e.clientY - resizeStart.value.y
  
  let newWidth = panel.size.width
  let newHeight = panel.size.height
  let newX = panel.position.x
  let newY = panel.position.y
  
  if (resizeDirection.value.includes('e')) {
    newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeStart.value.width + deltaX))
  }
  if (resizeDirection.value.includes('w')) {
    const proposedWidth = resizeStart.value.width - deltaX
    if (proposedWidth >= MIN_WIDTH && proposedWidth <= MAX_WIDTH) {
      newWidth = proposedWidth
      newX = panel.position.x + deltaX
    }
  }
  if (resizeDirection.value.includes('s')) {
    newHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, resizeStart.value.height + deltaY))
  }
  if (resizeDirection.value.includes('n')) {
    const proposedHeight = resizeStart.value.height - deltaY
    if (proposedHeight >= MIN_HEIGHT && proposedHeight <= MAX_HEIGHT) {
      newHeight = proposedHeight
      newY = panel.position.y + deltaY
    }
  }
  
  pdfStore.updatePanelSize(resizingPanelId.value, { width: newWidth, height: newHeight })
  pdfStore.updatePanelPosition(resizingPanelId.value, { x: newX, y: newY })
}

// 关闭面板
function closePanel(panelId: string) {
  pdfStore.closeTranslationPanelById(panelId)
}

// 重新翻译
async function retranslate(panel: TranslationPanelInstance) {
  const pdfId = libraryStore.currentDocumentId
  if (!pdfId || !panel.paragraphId) return
  
  pdfStore.setPanelLoading(panel.id, true)
  
  try {
    const result = await aiApi.translateParagraph(pdfId, panel.paragraphId, true)
    if (result.success) {
      pdfStore.setTranslation(panel.paragraphId, result.translation)
    }
  } catch (error) {
    console.error('Translation failed:', error)
  }
}

// 获取翻译
async function fetchTranslation(panel: TranslationPanelInstance) {
  const pdfId = libraryStore.currentDocumentId
  if (!pdfId || !panel.paragraphId || panel.translation) return
  
  pdfStore.setPanelLoading(panel.id, true)
  
  try {
    const result = await aiApi.translateParagraph(pdfId, panel.paragraphId)
    if (result.success) {
      pdfStore.setTranslation(panel.paragraphId, result.translation)
    }
  } catch (error) {
    console.error('Translation failed:', error)
    pdfStore.setTranslation(panel.paragraphId, '翻译失败，请重试')
  }
}

// 监听面板变化，自动请求翻译
watch(() => pdfStore.translationPanels.length, () => {
  pdfStore.translationPanels.forEach(panel => {
    if (!panel.translation && panel.isLoading) {
      fetchTranslation(panel)
    }
  })
}, { immediate: true })

// 监听PDF滚动，更新吸附面板位置
function onPdfScroll() {
  pdfStore.translationPanels.forEach(panel => {
    if (panel.snapMode === 'paragraph' && panel.snapTargetParagraphId) {
      const snapPos = calculateParagraphSnapPosition(panel.snapTargetParagraphId)
      if (snapPos) {
        pdfStore.updatePanelPosition(panel.id, {
          x: snapPos.left,
          y: snapPos.top
        })
      }
    }
  })
}

// 点击面板时聚焦
function focusPanel(panelId: string) {
  pdfStore.bringPanelToFront(panelId)
}

onMounted(() => {
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  
  const pdfContainer = document.querySelector('.pdf-scroll-container')
  if (pdfContainer) {
    pdfContainer.addEventListener('scroll', onPdfScroll)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  
  const pdfContainer = document.querySelector('.pdf-scroll-container')
  if (pdfContainer) {
    pdfContainer.removeEventListener('scroll', onPdfScroll)
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
  <template v-for="(panel, index) in pdfStore.translationPanels.filter(p => !p.isSidebarDocked)" :key="panel.id">
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
      <div class="panel-content flex-1 overflow-y-auto p-3 cursor-auto" @mousedown.stop>
        <!-- 加载中状态 -->
        <div v-if="panel.isLoading" class="flex flex-col items-center justify-center py-6">
          <div class="loading-spinner mb-2"></div>
          <span class="text-gray-400 dark:text-gray-500 text-xs">翻译中...</span>
        </div>
        
        <!-- 翻译内容 -->
        <div 
          v-else 
          class="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap"
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
  border: 2px dashed rgba(120, 140, 160, 0.5);
  border-radius: 6px;
  background: rgba(120, 140, 160, 0.08);
  transition: all 0.15s ease;
}

.snap-hint-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 10px;
  background: rgba(80, 100, 120, 0.85);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
}

/* 侧边栏吸附提示 */
.sidebar-snap-hint {
  background: linear-gradient(to left, rgba(120, 140, 160, 0.15), transparent);
  border-left: 2px dashed rgba(120, 140, 160, 0.4);
}

.sidebar-hint-text {
  position: absolute;
  top: 50%;
  right: 16px;
  transform: translateY(-50%) rotate(-90deg);
  padding: 4px 10px;
  background: rgba(80, 100, 120, 0.85);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
}
</style>
