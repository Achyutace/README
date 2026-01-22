<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { aiApi } from '../../api'
import { useLibraryStore } from '../../stores/library'

const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

// 拖动相关状态
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const panelRef = ref<HTMLElement | null>(null)

// 面板位置
const position = computed(() => pdfStore.translationPanel.position)

// 面板尺寸（可调整）
const panelWidth = ref(320)
const panelHeight = ref(280)
const minWidth = 200
const maxWidth = 600
const minHeight = 150
const maxHeight = 500

// 调整大小相关状态
const isResizing = ref(false)
const resizeDirection = ref<string>('')
const resizeStart = ref({ x: 0, y: 0, width: 0, height: 0 })

// 吸附相关状态
const isNearSnapTarget = ref(false)
const snappedToParagraph = ref(false)
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null)

// 计算吸附目标位置
function calculateSnapPosition() {
  const paragraphId = pdfStore.translationPanel.paragraphId
  if (!paragraphId) return null
  
  const paragraphs = pdfStore.paragraphs
  const paragraph = paragraphs.find(p => p.id === paragraphId)
  if (!paragraph) return null
  
  // 找到段落所在页面的容器
  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement
  if (!pageElement) return null
  
  const pageRect = pageElement.getBoundingClientRect()
  const canvas = pageElement.querySelector('canvas')
  if (!canvas) return null
  
  // 计算段落在视口中的实际位置
  const scaleX = canvas.offsetWidth / canvas.width
  const scaleY = canvas.offsetHeight / canvas.height
  
  return {
    left: pageRect.left + paragraph.bbox.x0 * scaleX,
    top: pageRect.top + paragraph.bbox.y0 * scaleY,
    width: paragraph.bbox.width * scaleX,
    height: paragraph.bbox.height * scaleY,
    pageElement
  }
}

// 开始拖动（只在标题栏）
function startDrag(e: MouseEvent) {
  // 只允许从标题栏拖动
  if (!(e.target as HTMLElement).closest('.panel-header')) return
  
  isDragging.value = true
  snappedToParagraph.value = false // 开始拖动时取消吸附
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  e.preventDefault()
}

// 拖动中
function onDrag(e: MouseEvent) {
  if (isResizing.value) {
    onResize(e)
    return
  }
  
  if (!isDragging.value) return
  
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  
  // 计算吸附目标
  const snapPos = calculateSnapPosition()
  if (snapPos) {
    snapTargetRect.value = snapPos
    // 检查是否接近吸附区域
    const distance = Math.sqrt(
      Math.pow(newX - snapPos.left, 2) + 
      Math.pow(newY - snapPos.top, 2)
    )
    isNearSnapTarget.value = distance < 80
  }
  
  // 限制在视口内
  const maxX = window.innerWidth - panelWidth.value
  const maxY = window.innerHeight - panelHeight.value
  
  pdfStore.updateTranslationPanelPosition({
    x: Math.max(0, Math.min(maxX, newX)),
    y: Math.max(0, Math.min(maxY, newY))
  })
}

// 停止拖动
function stopDrag() {
  if (isDragging.value && isNearSnapTarget.value && snapTargetRect.value) {
    // 执行吸附
    snappedToParagraph.value = true
    pdfStore.updateTranslationPanelPosition({
      x: snapTargetRect.value.left,
      y: snapTargetRect.value.top
    })
    // 调整面板大小匹配段落
    panelWidth.value = Math.max(minWidth, Math.min(maxWidth, snapTargetRect.value.width))
  }
  
  isDragging.value = false
  isNearSnapTarget.value = false
  isResizing.value = false
  resizeDirection.value = ''
}

// 开始调整大小
function startResize(e: MouseEvent, direction: string) {
  e.stopPropagation()
  e.preventDefault()
  isResizing.value = true
  resizeDirection.value = direction
  resizeStart.value = {
    x: e.clientX,
    y: e.clientY,
    width: panelWidth.value,
    height: panelHeight.value
  }
}

// 调整大小中
function onResize(e: MouseEvent) {
  if (!isResizing.value) return
  
  const deltaX = e.clientX - resizeStart.value.x
  const deltaY = e.clientY - resizeStart.value.y
  
  // 根据拖动方向调整
  if (resizeDirection.value.includes('e')) {
    panelWidth.value = Math.max(minWidth, Math.min(maxWidth, resizeStart.value.width + deltaX))
  }
  if (resizeDirection.value.includes('w')) {
    const newWidth = resizeStart.value.width - deltaX
    if (newWidth >= minWidth && newWidth <= maxWidth) {
      panelWidth.value = newWidth
      pdfStore.updateTranslationPanelPosition({
        x: position.value.x + deltaX,
        y: position.value.y
      })
    }
  }
  if (resizeDirection.value.includes('s')) {
    panelHeight.value = Math.max(minHeight, Math.min(maxHeight, resizeStart.value.height + deltaY))
  }
  if (resizeDirection.value.includes('n')) {
    const newHeight = resizeStart.value.height - deltaY
    if (newHeight >= minHeight && newHeight <= maxHeight) {
      panelHeight.value = newHeight
      pdfStore.updateTranslationPanelPosition({
        x: position.value.x,
        y: position.value.y + deltaY
      })
    }
  }
}

// 监听PDF滚动，更新吸附位置
function onPdfScroll() {
  if (!snappedToParagraph.value) return
  
  const snapPos = calculateSnapPosition()
  if (snapPos) {
    pdfStore.updateTranslationPanelPosition({
      x: snapPos.left,
      y: snapPos.top
    })
  }
}

// 关闭面板
function closePanel() {
  pdfStore.closeTranslationPanel()
}

// 监听面板打开，自动请求翻译
watch(() => pdfStore.translationPanel.isVisible, async (visible) => {
  if (visible && !pdfStore.translationPanel.translation && pdfStore.translationPanel.paragraphId) {
    await fetchTranslation()
  }
})

// 获取翻译
async function fetchTranslation() {
  const { paragraphId } = pdfStore.translationPanel
  const pdfId = libraryStore.currentDocumentId
  
  if (!pdfId || !paragraphId) return
  
  pdfStore.setTranslationLoading(true)
  
  try {
    const result = await aiApi.translateParagraph(pdfId, paragraphId)
    if (result.success) {
      pdfStore.setTranslation(paragraphId, result.translation)
    }
  } catch (error) {
    console.error('Translation failed:', error)
    pdfStore.setTranslation(paragraphId, '翻译失败，请重试')
  }
}

// 重新翻译
async function retranslate() {
  const { paragraphId } = pdfStore.translationPanel
  const pdfId = libraryStore.currentDocumentId
  
  if (!pdfId || !paragraphId) return
  
  pdfStore.setTranslationLoading(true)
  
  try {
    const result = await aiApi.translateParagraph(pdfId, paragraphId, true)
    if (result.success) {
      pdfStore.setTranslation(paragraphId, result.translation)
    }
  } catch (error) {
    console.error('Translation failed:', error)
  }
}

onMounted(() => {
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  
  // 监听PDF容器的滚动事件
  const pdfContainer = document.querySelector('.pdf-container')
  if (pdfContainer) {
    pdfContainer.addEventListener('scroll', onPdfScroll)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  
  const pdfContainer = document.querySelector('.pdf-container')
  if (pdfContainer) {
    pdfContainer.removeEventListener('scroll', onPdfScroll)
  }
})
</script>

<template>
  <!-- 拖动时显示的吸附提示框 -->
  <div
    v-if="isDragging && snapTargetRect"
    class="snap-hint fixed z-[999] pointer-events-none"
    :class="{ 'snap-hint-active': isNearSnapTarget }"
    :style="{
      left: snapTargetRect.left + 'px',
      top: snapTargetRect.top + 'px',
      width: snapTargetRect.width + 'px',
      height: snapTargetRect.height + 'px',
    }"
  >
    <div class="snap-hint-text">释放以吸附到原文位置</div>
  </div>

  <div
    v-if="pdfStore.translationPanel.isVisible"
    ref="panelRef"
    class="translation-panel fixed z-[1000] bg-white dark:bg-[#2d2d30] rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden select-none"
    :style="{
      left: position.x + 'px',
      top: position.y + 'px',
      width: panelWidth + 'px',
      height: panelHeight + 'px',
    }"
    :class="{ 'is-snapped': snappedToParagraph }"
  >
    <!-- 头部 - 可拖动区域 -->
    <div 
      class="panel-header flex items-center justify-between px-3 py-2 bg-gradient-to-r from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700 text-white cursor-move"
      @mousedown="startDrag"
    >
      <div class="flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
        </svg>
        <span class="text-sm font-medium">段落翻译</span>
      </div>
      <div class="flex items-center gap-1">
        <!-- 重新翻译按钮 -->
        <button
          @click.stop="retranslate"
          class="p-1 hover:bg-white/20 rounded transition-colors"
          title="重新翻译"
          :disabled="pdfStore.translationPanel.isLoading"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': pdfStore.translationPanel.isLoading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
        <!-- 关闭按钮 -->
        <button
          @click.stop="closePanel"
          class="p-1 hover:bg-white/20 rounded transition-colors"
          title="关闭"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
    
    <!-- 内容区域 - 可滚动 -->
    <div class="panel-content flex-1 overflow-y-auto p-3 cursor-auto" @mousedown.stop>
      <!-- 加载中状态 -->
      <div v-if="pdfStore.translationPanel.isLoading" class="flex flex-col items-center justify-center py-8">
        <div class="loading-spinner mb-3"></div>
        <span class="text-gray-500 dark:text-gray-400 text-sm">正在翻译...</span>
      </div>
      
      <!-- 翻译内容 -->
      <div v-else class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
        {{ pdfStore.translationPanel.translation || '暂无翻译' }}
      </div>
    </div>
    
    <!-- 底部状态提示 -->
    <div class="px-3 py-1.5 bg-gray-50 dark:bg-[#252526] border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
      <span class="text-xs text-gray-400 dark:text-gray-500">
        {{ snappedToParagraph ? '已吸附到原文' : '拖动标题栏移动 | 拖动边框调整大小' }}
      </span>
      <span v-if="snappedToParagraph" class="text-xs text-blue-500">跟随滚动</span>
    </div>
    
    <!-- 调整大小的边框 -->
    <!-- 左边框 -->
    <div class="resize-handle resize-w" @mousedown="startResize($event, 'w')"></div>
    <!-- 右边框 -->
    <div class="resize-handle resize-e" @mousedown="startResize($event, 'e')"></div>
    <!-- 下边框 -->
    <div class="resize-handle resize-s" @mousedown="startResize($event, 's')"></div>
    <!-- 左下角 -->
    <div class="resize-handle resize-sw" @mousedown="startResize($event, 'sw')"></div>
    <!-- 右下角 -->
    <div class="resize-handle resize-se" @mousedown="startResize($event, 'se')"></div>
  </div>
</template>

<style scoped>
.translation-panel {
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15), 0 8px 16px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
}

.translation-panel.is-snapped {
  border: 2px solid #3b82f6;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 自定义滚动条 */
.panel-content::-webkit-scrollbar {
  width: 6px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
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
  top: 40px;
  bottom: 10px;
  width: 6px;
  cursor: ew-resize;
}

.resize-e {
  right: 0;
  top: 40px;
  bottom: 10px;
  width: 6px;
  cursor: ew-resize;
}

.resize-s {
  bottom: 0;
  left: 10px;
  right: 10px;
  height: 6px;
  cursor: ns-resize;
}

.resize-sw {
  left: 0;
  bottom: 0;
  width: 12px;
  height: 12px;
  cursor: nesw-resize;
}

.resize-se {
  right: 0;
  bottom: 0;
  width: 12px;
  height: 12px;
  cursor: nwse-resize;
}

.resize-handle:hover {
  background: rgba(59, 130, 246, 0.1);
}

/* 吸附提示框 */
.snap-hint {
  border: 2px dashed #9ca3af;
  border-radius: 8px;
  background: rgba(156, 163, 175, 0.1);
  transition: all 0.2s ease;
}

.snap-hint-active {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.15);
}

.snap-hint-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 12px;
  border-radius: 4px;
  white-space: nowrap;
}
</style>
