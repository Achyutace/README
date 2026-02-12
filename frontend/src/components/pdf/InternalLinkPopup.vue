<script setup lang="ts">
// ------------------------- 导入依赖与状态 -------------------------
import { ref, computed, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { getParagraphByCoords } from '../../utils/PdfRender'
import { clamp } from '@vueuse/core'

// 初始化 PDF store 实例
const pdfStore = usePdfStore()

// 拖拽相关状态
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// 从 store 获取数据
const isVisible = computed(() => pdfStore.internalLinkPopup.isVisible)
const destCoords = computed(() => pdfStore.internalLinkPopup.destCoords)
const position = computed(() => pdfStore.internalLinkPopup.position)
const paragraphs = computed(() => pdfStore.paragraphs)

// 根据坐标获取对应的段落
const targetParagraph = computed(() => {
  if (!destCoords.value) return null
  const { page, x, y } = destCoords.value
  return getParagraphByCoords(page, x, y, paragraphs.value)
})

// 格式化位置信息文本
const positionText = computed(() => {
  if (!destCoords.value) return ''
  return `第 ${destCoords.value.page} 页`
})

// 格式化坐标信息
const coordinateText = computed(() => {
  if (!destCoords.value) return ''
  const { x, y } = destCoords.value
  const xStr = x !== null ? x.toFixed(1) : '-'
  const yStr = y !== null ? y.toFixed(1) : '-'
  return `X: ${xStr}, Y: ${yStr}`
})

// 拖动开始函数
function startDrag(e: MouseEvent) {
  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

// 拖动中函数
function onDrag(e: MouseEvent) {
  if (!isDragging.value) return
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  const clampedX = clamp(newX, 0, window.innerWidth - 280)
  const clampedY = clamp(newY, 0, window.innerHeight - 100)
  pdfStore.updateInternalLinkPopupPosition({ x: clampedX, y: clampedY })
}

// 拖动结束函数
function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭弹窗
function closePopup() {
  pdfStore.closeInternalLinkPopup()
}

// 组件卸载时清理
watch(isVisible, (visible) => {
  if (!visible) {
    isDragging.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="internal-link-popup fixed z-[9999] w-[320px] bg-white dark:bg-[#1e1e1e] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
      :style="{ left: position.x + 'px', top: position.y + 'px' }"
    >
      <!-- 拖动头部 -->
      <div
        class="flex items-center justify-between px-3 py-2 bg-gray-100 dark:bg-gray-800 cursor-move select-none border-b border-gray-200 dark:border-gray-700"
        @mousedown="startDrag"
      >
        <span class="text-xs font-medium text-gray-600 dark:text-gray-400">内部引用</span>
        <button
          @click="closePopup"
          class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors"
        >
          <svg class="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- 内容区域 -->
      <div class="p-3 space-y-3">
        <!-- 段落 ID -->
        <div class="space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-xs text-gray-500 dark:text-gray-400">引用段落</span>
            <span class="text-xs text-blue-600 dark:text-blue-400">{{ positionText }}</span>
          </div>
          <div 
            class="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 px-3 py-2.5 rounded max-h-[200px] overflow-y-auto leading-relaxed"
            :class="{ 'italic text-gray-400': !targetParagraph }"
          >
            {{ targetParagraph?.content || '无法定位到具体段落内容' }}
          </div>
          <!-- 坐标信息 -->
          <div class="text-xs font-mono text-gray-500 dark:text-gray-500 mt-1.5">
            {{ coordinateText }}
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.internal-link-popup {
  animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
.dark ::-webkit-scrollbar-thumb {
  background: #4b5563;
}
.dark ::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}
</style>
