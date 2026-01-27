<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、PDF store、AI API 及文库 store
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue' // 导入Vue的响应式API、计算属性和生命周期钩子
import { usePdfStore } from '../../stores/pdf' // 导入PDF store，用于管理PDF相关状态
import { aiApi } from '../../api' // 导入AI API，用于调用翻译服务
import { useLibraryStore } from '../../stores/library' // 导入文库 store，用于管理文档库状态

const pdfStore = usePdfStore() // 获取PDF store实例
const libraryStore = useLibraryStore() // 获取文库 store实例

// 拖动相关状态
const isDragging = ref(false) // 是否正在拖动面板
const dragOffset = ref({ x: 0, y: 0 }) // 拖动时的偏移量
const panelRef = ref<HTMLElement | null>(null) // 面板DOM元素引用

// 面板位置
const position = computed(() => pdfStore.translationPanel.position) // 计算属性，获取面板当前位置

// 面板尺寸（可调整）
const panelWidth = ref(320) // 面板宽度
const panelHeight = ref(280) // 面板高度
const minWidth = 200 // 最小宽度
const maxWidth = 600 // 最大宽度
const minHeight = 150 // 最小高度
const maxHeight = 500 // 最大高度

// 调整大小相关状态
const isResizing = ref(false) // 是否正在调整大小
const resizeDirection = ref<string>('') // 调整大小的方向
const resizeStart = ref({ x: 0, y: 0, width: 0, height: 0 }) // 调整大小开始时的状态

// 吸附相关状态
const isNearSnapTarget = ref(false) // 是否接近吸附目标
const snappedToParagraph = ref(false) // 是否已吸附到段落
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null) // 吸附目标的矩形区域

// 计算吸附目标位置
function calculateSnapPosition() { // 计算段落的吸附位置
  const paragraphId = pdfStore.translationPanel.paragraphId // 获取面板关联的段落ID
  if (!paragraphId) return null // 如果没有段落ID，返回null
  
  const paragraphs = pdfStore.paragraphs // 获取所有段落数据
  const paragraph = paragraphs.find(p => p.id === paragraphId) // 查找指定段落
  if (!paragraph) return null // 如果没找到段落，返回null
  
  // 找到段落所在页面的容器
  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement // 查找页面元素
  if (!pageElement) return null // 如果页面元素不存在，返回null

  const pageRect = pageElement.getBoundingClientRect() // 获取页面边界矩形
  const canvas = pageElement.querySelector('canvas') // 查找页面中的canvas元素
  if (!canvas) return null // 如果canvas不存在，返回null
  
  // 计算段落在视口中的实际位置
  const scaleX = canvas.offsetWidth / canvas.width // 计算X方向缩放因子
  const scaleY = canvas.offsetHeight / canvas.height // 计算Y方向缩放因子
  
  return { // 返回段落在屏幕上的位置信息
    left: pageRect.left + paragraph.bbox.x0 * scaleX, // 左边距
    top: pageRect.top + paragraph.bbox.y0 * scaleY, // 上边距
    width: paragraph.bbox.width * scaleX, // 宽度
    height: paragraph.bbox.height * scaleY, // 高度
    pageElement // 页面元素引用
  }
}

// 开始拖动（只在标题栏）
function startDrag(e: MouseEvent) { // 鼠标按下开始拖动
  // 只允许从标题栏拖动
  if (!(e.target as HTMLElement).closest('.panel-header')) return // 检查是否在标题栏点击
  
  isDragging.value = true // 设置拖动状态
  snappedToParagraph.value = false // 开始拖动时取消吸附
  dragOffset.value = { // 计算拖动偏移量
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  e.preventDefault() // 阻止默认事件
}

// 拖动中
function onDrag(e: MouseEvent) { // 鼠标移动时的拖动处理
  if (isResizing.value) { // 如果正在调整大小
    onResize(e) // 调用调整大小函数
    return
  }
  
  if (!isDragging.value) return // 如果没有拖动，返回
  
  const newX = e.clientX - dragOffset.value.x // 计算新的X位置
  const newY = e.clientY - dragOffset.value.y // 计算新的Y位置
  
  // 计算吸附目标
  const snapPos = calculateSnapPosition() // 获取吸附位置
  if (snapPos) { // 如果有吸附位置
    snapTargetRect.value = snapPos // 设置吸附目标矩形
    // 检查是否接近吸附区域（增大吸附范围到120px）
    const distance = Math.sqrt( // 计算距离
      Math.pow(newX - snapPos.left, 2) +
      Math.pow(newY - snapPos.top, 2)
    )
    isNearSnapTarget.value = distance < 120 // 判断是否接近吸附区域
  }
  
  // 限制在视口内
  const maxX = window.innerWidth - panelWidth.value // 计算最大X位置
  const maxY = window.innerHeight - panelHeight.value // 计算最大Y位置
  
  pdfStore.updateTranslationPanelPosition({ // 更新面板位置
    x: Math.max(0, Math.min(maxX, newX)), // 限制X在0到maxX之间
    y: Math.max(0, Math.min(maxY, newY)) // 限制Y在0到maxY之间
  })
}

// 停止拖动
function stopDrag() { // 鼠标释放停止拖动
  if (isDragging.value && isNearSnapTarget.value && snapTargetRect.value) { // 如果拖动中且接近吸附目标
    // 执行吸附（稍微偏移，避免完全覆盖原文）
    snappedToParagraph.value = true // 设置吸附状态
    pdfStore.updateTranslationPanelPosition({ // 更新位置到吸附点
      x: snapTargetRect.value.left + 4, // 稍微偏移4px
      y: snapTargetRect.value.top + 4
    })
    // 调整面板大小匹配段落（稍微缩小，让原文边缘可见）
    panelWidth.value = Math.max(minWidth, Math.min(maxWidth, snapTargetRect.value.width - 8)) // 宽度减8px
  }

  isDragging.value = false // 重置拖动状态
  isNearSnapTarget.value = false // 重置吸附状态
  isResizing.value = false // 重置调整大小状态
  resizeDirection.value = '' // 重置调整方向
}

// 开始调整大小
function startResize(e: MouseEvent, direction: string) { // 开始调整面板大小
  e.stopPropagation() // 阻止事件冒泡
  e.preventDefault() // 阻止默认事件
  isResizing.value = true // 设置调整大小状态
  resizeDirection.value = direction // 设置调整方向
  resizeStart.value = { // 记录开始时的状态
    x: e.clientX,
    y: e.clientY,
    width: panelWidth.value,
    height: panelHeight.value
  }
}

// 调整大小中
function onResize(e: MouseEvent) { // 鼠标移动时的调整大小处理
  if (!isResizing.value) return // 如果没有调整大小，返回
  
  const deltaX = e.clientX - resizeStart.value.x // 计算X变化量
  const deltaY = e.clientY - resizeStart.value.y // 计算Y变化量
  
  // 根据拖动方向调整
  if (resizeDirection.value.includes('e')) { // 东向调整（右边框）
    panelWidth.value = Math.max(minWidth, Math.min(maxWidth, resizeStart.value.width + deltaX)) // 更新宽度
  }
  if (resizeDirection.value.includes('w')) { // 西向调整（左边框）
    const newWidth = resizeStart.value.width - deltaX // 计算新宽度
    if (newWidth >= minWidth && newWidth <= maxWidth) { // 检查范围
      panelWidth.value = newWidth // 设置新宽度
      pdfStore.updateTranslationPanelPosition({ // 更新位置
        x: position.value.x + deltaX,
        y: position.value.y
      })
    }
  }
  if (resizeDirection.value.includes('s')) { // 南向调整（下边框）
    panelHeight.value = Math.max(minHeight, Math.min(maxHeight, resizeStart.value.height + deltaY)) // 更新高度
  }
  if (resizeDirection.value.includes('n')) { // 北向调整（上边框）
    const newHeight = resizeStart.value.height - deltaY // 计算新高度
    if (newHeight >= minHeight && newHeight <= maxHeight) { // 检查范围
      panelHeight.value = newHeight // 设置新高度
      pdfStore.updateTranslationPanelPosition({ // 更新位置
        x: position.value.x,
        y: position.value.y + deltaY
      })
    }
  }
}

// 监听PDF滚动，更新吸附位置
function onPdfScroll() { // PDF滚动事件处理
  if (!snappedToParagraph.value) return // 如果没有吸附到段落，返回

  const snapPos = calculateSnapPosition() // 重新计算吸附位置
  if (snapPos) { // 如果计算成功
    pdfStore.updateTranslationPanelPosition({ // 更新面板位置
      x: snapPos.left + 4, // 保持偏移
      y: snapPos.top + 4
    })
  }
}

// 关闭面板
function closePanel() { // 关闭翻译面板
  pdfStore.closeTranslationPanel() // 调用store关闭面板
}

// 监听面板打开，自动请求翻译
watch(() => pdfStore.translationPanel.isVisible, async (visible) => { // 监听面板可见性变化
  if (visible && !pdfStore.translationPanel.translation && pdfStore.translationPanel.paragraphId) { // 如果面板打开且没有翻译
    await fetchTranslation() // 获取翻译
  }
})

// 获取翻译
async function fetchTranslation() { // 异步获取翻译内容
  const { paragraphId } = pdfStore.translationPanel // 获取段落ID
  const pdfId = libraryStore.currentDocumentId // 获取文档ID
  
  if (!pdfId || !paragraphId) return // 如果缺少必要信息，返回
  
  pdfStore.setTranslationLoading(true) // 设置加载状态
  
  try {
    const result = await aiApi.translateParagraph(pdfId, paragraphId) // 调用API翻译段落
    if (result.success) { // 如果翻译成功
      pdfStore.setTranslation(paragraphId, result.translation) // 更新翻译内容
    }
  } catch (error) {
    console.error('Translation failed:', error) // 记录错误
    pdfStore.setTranslation(paragraphId, '翻译失败，请重试') // 设置错误消息
  }
}

// 重新翻译
async function retranslate() { // 异步重新翻译
  const { paragraphId } = pdfStore.translationPanel // 获取段落ID
  const pdfId = libraryStore.currentDocumentId // 获取文档ID
  
  if (!pdfId || !paragraphId) return // 如果缺少必要信息，返回
  
  pdfStore.setTranslationLoading(true) // 设置加载状态
  
  try {
    const result = await aiApi.translateParagraph(pdfId, paragraphId, true) // 调用API重新翻译（强制刷新）
    if (result.success) { // 如果翻译成功
      pdfStore.setTranslation(paragraphId, result.translation) // 更新翻译内容
    }
  } catch (error) {
    console.error('Translation failed:', error) // 记录错误
  }
}

onMounted(() => { // 组件挂载时
  document.addEventListener('mousemove', onDrag) // 添加鼠标移动监听
  document.addEventListener('mouseup', stopDrag) // 添加鼠标释放监听
  
  // 监听PDF容器的滚动事件
  const pdfContainer = document.querySelector('.pdf-container') // 查找PDF容器
  if (pdfContainer) { // 如果找到
    pdfContainer.addEventListener('scroll', onPdfScroll) // 添加滚动监听
  }
})

onBeforeUnmount(() => { // 组件卸载前
  document.removeEventListener('mousemove', onDrag) // 移除鼠标移动监听
  document.removeEventListener('mouseup', stopDrag) // 移除鼠标释放监听
  
  const pdfContainer = document.querySelector('.pdf-container') // 查找PDF容器
  if (pdfContainer) { // 如果找到
    pdfContainer.removeEventListener('scroll', onPdfScroll) // 移除滚动监听

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
