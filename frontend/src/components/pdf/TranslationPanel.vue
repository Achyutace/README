<script setup lang="ts">
// =============================================================================
// TranslationPanel.vue
//
// 功能概述：单例段落翻译面板（用于显示并管理单个段落的翻译结果）。
// - 与 `translationStore.translationPanel` 交互：读取/更新面板的可见性、位置、加载状态和翻译内容。
// - 支持拖拽并可“吸附”到某个段落（释放时对齐并调整宽度），吸附后会随 PDF 滚动跟随段落。
// - 支持调整大小、自动在打开时请求翻译，以及手动触发重新翻译。
// 设计原则：保持面板轻量且专注于单段落场景（与多面板实现分离），便于用户单点查看与临时注释。
// 交互要点：
// - 拖动过程中会计算是否接近段落吸附目标并显示提示，释放后完成吸附逻辑。
// - 面板位置/尺寸的变更会同步回 store，以便全局状态一致。
// - 监听 PDF 容器滚动以便在已吸附时持续更新位置，防止错位。
// =============================================================================
/* 导入：Vue 响应式 API、PDF store、可复用的拖拽/缩放 hook、翻译 composable */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { useTranslationStore } from '../../stores/translation'
import DraggablePanel from '../common/DraggablePanel.vue'
import { clip } from '../../utils/CommonFunction'

const pdfStore = usePdfStore()
const translationStore = useTranslationStore()

// 面板位置
const position = computed(() => translationStore.translationPanel.position)

// 面板尺寸（可调整），默认320x280
const panelWidth = ref(320)
const panelHeight = ref(280)

// 面板大小限制
const minWidth = 200
const maxWidth = 600
const minHeight = 150
const maxHeight = 500

// 吸附相关状态
const isNearSnapTarget = ref(false)
const snappedToParagraph = ref(false)
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null)

// 使用通用的 DraggablePanel 组件来处理拖拽与缩放，父组件通过事件处理吸附逻辑
const isDragging = ref(false)
const isResizing = ref(false)

// 本地定时器（用于在收到 size 更新后短暂标记 isResizing）
let updateSizeTimer: number | null = null

function onDragStart() {
  isDragging.value = true
  snappedToParagraph.value = false
}

function onDragEnd() {
  isDragging.value = false
  if (isNearSnapTarget.value && snapTargetRect.value) {
    snappedToParagraph.value = true
    translationStore.updateTranslationPanelPosition({
      x: snapTargetRect.value.left + 4,
      y: snapTargetRect.value.top + 4
    })
    panelWidth.value = clip(snapTargetRect.value.width - 8, minWidth, maxWidth)
  }
  isNearSnapTarget.value = false
}

function onUpdatePosition(newPos: { x: number; y: number }) {
  // 如果在缩放中，略过吸附判断
  if (isResizing.value) return

  // 拖动期间检测是否靠近吸附目标
  if (isDragging.value) {
    const snapPos = calculateSnapPosition()
    if (snapPos) {
      snapTargetRect.value = snapPos
      const distance = Math.hypot(newPos.x - snapPos.left, newPos.y - snapPos.top)
      isNearSnapTarget.value = distance < 120
    } else {
      isNearSnapTarget.value = false
    }
  } else {
    isNearSnapTarget.value = false
  }

  // 限制在视口内并同步到 store
  const maxX = window.innerWidth - panelWidth.value
  const maxY = window.innerHeight - panelHeight.value
  translationStore.updateTranslationPanelPosition({
    x: clip(newPos.x, 0, maxX),
    y: clip(newPos.y, 0, maxY)
  })
}

function onUpdateSize(size: { width: number; height: number }) {
  // 标记为正在缩放，使用短延时模拟 resize-end 事件
  isResizing.value = true
  panelWidth.value = size.width
  panelHeight.value = size.height

  // 清理并重建局部定时器，避免在函数上挂属性并解决 TS 的调用解析问题
  if (updateSizeTimer) window.clearTimeout(updateSizeTimer)
  updateSizeTimer = window.setTimeout(() => {
    isResizing.value = false
    updateSizeTimer = null
  }, 120)
}



// 计算吸附目标位置（将段落 bbox 从 PDF 原始坐标映射到当前渲染坐标）
// 说明：translationStore.translationPanel.paragraphId 指向要吸附的段落。
// - 读取段落的 bbox（x0,y0,width,height），结合页面 canvas 的实际渲染尺寸，
//   计算出在屏幕上的精确像素位置用于吸附显示。
// - 返回 left/top/width/height 以及 pageElement（用于后续滚动定位）。
function calculateSnapPosition() {
  const paragraphId = translationStore.translationPanel.paragraphId
  if (!paragraphId) return null
  
  const paragraphs = pdfStore.paragraphs
  const paragraph = paragraphs.find(p => p.id === paragraphId)
  if (!paragraph) return null
  
  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement
  if (!pageElement) return null

  const pageRect = pageElement.getBoundingClientRect()
  const canvas = pageElement.querySelector('canvas')
  if (!canvas) return null
  
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


// 监听PDF滚动，更新吸附位置（当面板已吸附时，使面板随页面滚动而移动以保持对齐）
function onPdfScroll() { // PDF滚动事件处理
  if (!snappedToParagraph.value) return // 如果没有吸附到段落，返回

  const snapPos = calculateSnapPosition() // 重新计算吸附位置
  if (snapPos) { // 如果计算成功
    translationStore.updateTranslationPanelPosition({ // 更新面板位置
      x: snapPos.left + 4, // 保持偏移
      y: snapPos.top + 4
    })
  }
}

// 关闭面板
function closePanel() { // 关闭翻译面板
  translationStore.closeTranslationPanel() // 调用store关闭面板
}

// 监听面板打开，自动请求翻译
watch(() => translationStore.translationPanel.isVisible, async (visible) => {
  if (visible && !translationStore.translationPanel.translation && translationStore.translationPanel.paragraphId) {
    await fetchTranslation()
  }
})

// 获取翻译（向后端请求指定段落翻译，并把结果写回 store，处理加载状态与错误提示）
async function fetchTranslation() {
  const { paragraphId } = translationStore.translationPanel
  
  if (!paragraphId) return
  
  translationStore.setTranslationLoading(true)
  
  const translation = await translationStore.translateParagraph(paragraphId)
  if (translation) {
    translationStore.setTranslation(paragraphId, translation)
  } else {
    translationStore.setTranslation(paragraphId, '翻译失败，请重试')
  }
}

// 重新翻译
async function retranslate() {
  const { paragraphId } = translationStore.translationPanel
  
  if (!paragraphId) return
  
  translationStore.setTranslationLoading(true)
  
  const translation = await translationStore.translateParagraph(paragraphId, true)
  if (translation) {
    translationStore.setTranslation(paragraphId, translation)
  }
}

onMounted(() => {
  // 监听PDF容器的滚动事件
  const pdfContainer = document.querySelector('.pdf-container')
  if (pdfContainer) {
    pdfContainer.addEventListener('scroll', onPdfScroll)
  }
})

onBeforeUnmount(() => {
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

  <DraggablePanel
    v-if="translationStore.translationPanel.isVisible"
    :initialPosition="position"
    :initialSize="{ width: panelWidth, height: panelHeight }"
    :minWidth="minWidth"
    :maxWidth="maxWidth"
    :minHeight="minHeight"
    :maxHeight="maxHeight"
    class="translation-panel fixed z-[1000] bg-white dark:bg-[#2d2d30] rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden select-none"
    :class="{ 'is-snapped': snappedToParagraph }"
    @update:position="onUpdatePosition"
    @update:size="onUpdateSize"
    @drag-start="onDragStart"
    @drag-end="onDragEnd"
    @close="closePanel"
  >
    <template #header-actions>
      <button
        @click.stop="retranslate"
        class="p-1 hover:bg-white/20 rounded transition-colors"
        title="重新翻译"
        :disabled="translationStore.translationPanel.isLoading"
      >
        <svg class="w-4 h-4" :class="{ 'animate-spin': translationStore.translationPanel.isLoading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
      <button
        @click.stop="closePanel"
        class="p-1 hover:bg-white/20 rounded transition-colors"
        title="关闭"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </template>

    <div class="panel-content flex-1 overflow-y-auto p-3 cursor-auto" @mousedown.stop>
      <div v-if="translationStore.translationPanel.isLoading" class="flex flex-col items-center justify-center py-8">
        <div class="loading-spinner mb-3"></div>
        <span class="text-gray-500 dark:text-gray-400 text-sm">正在翻译...</span>
      </div>
      <div v-else class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
        {{ translationStore.translationPanel.translation || '暂无翻译' }}
      </div>
    </div>

    <template #footer>
      <div class="px-3 py-1.5 bg-gray-50 dark:bg-[#252526] border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <span class="text-xs text-gray-400 dark:text-gray-500">
          {{ snappedToParagraph ? '已吸附到原文' : '拖动标题栏移动 | 拖动边框调整大小' }}
        </span>
        <span v-if="snappedToParagraph" class="text-xs text-blue-500">跟随滚动</span>
      </div>
    </template>

  </DraggablePanel>
</template>

<style scoped>
.translation-panel {
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15), 0 8px 16px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.92) !important;
}

.dark .translation-panel {
  background: rgba(45, 45, 48, 0.92) !important;
}

.translation-panel.is-snapped {
  border: 2px solid #3b82f6;
  background: rgba(255, 255, 255, 0.85) !important;
}

.dark .translation-panel.is-snapped {
  background: rgba(45, 45, 48, 0.85) !important;
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
  transition: all 0.15s ease;
}

.snap-hint-active {
  border-color: #3b82f6;
  border-width: 3px;
  background: rgba(59, 130, 246, 0.2);
  box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
}

.snap-hint-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 8px 16px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
  white-space: nowrap;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
