<script setup lang="ts">
// ------------------------- 导入依赖与状态 -------------------------
import { ref, computed, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
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

// 格式化显示的坐标信息（PDF 目标坐标）
const coordinateInfo = computed(() => {
  if (!destCoords.value) return ''
  const { x, y, type } = destCoords.value
  
  // 根据目标类型显示不同的坐标信息
  switch (type) {
    case 'XYZ':
      if (x !== null && y !== null) {
        return `X: ${x.toFixed(3)}, Y: ${y.toFixed(3)}`
      } else if (x !== null) {
        return `X: ${x.toFixed(3)}`
      } else if (y !== null) {
        return `Y: ${y.toFixed(3)}`
      }
      return '页面顶部'
    case 'FitH':
    case 'FitBH':
      return y !== null ? `Y: ${y.toFixed(3)} (水平适应)` : '水平适应'
    case 'FitV':
    case 'FitBV':
      return x !== null ? `X: ${x.toFixed(3)} (垂直适应)` : '垂直适应'
    case 'FitR':
      if (x !== null && y !== null) {
        return `X: ${x.toFixed(3)}, Y: ${y.toFixed(3)} (区域适应)`
      }
      return '区域适应'
    case 'Fit':
    case 'FitB':
      return '适应页面'
    default:
      return x !== null || y !== null 
        ? `X: ${x?.toFixed(3) ?? '-'}, Y: ${y?.toFixed(3) ?? '-'}`
        : '默认位置'
  }
})

// 格式化位置信息文本
const positionText = computed(() => {
  if (!destCoords.value) return ''
  return `第 ${destCoords.value.page} 页`
})

// 缩放信息
const zoomText = computed(() => {
  if (!destCoords.value) return null
  const { zoom } = destCoords.value
  if (zoom !== null && zoom > 0) {
    return `${(zoom * 100).toFixed(0)}%`
  }
  return null
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

// 跳转到目标页面
function goToPage() {
  if (destCoords.value) {
    pdfStore.goToPage(destCoords.value.page)
  }
  closePopup()
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
      class="internal-link-popup fixed z-[9999] w-[280px] bg-white dark:bg-[#1e1e1e] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
      :style="{ left: position.x + 'px', top: position.y + 'px' }"
    >
      <!-- 拖动头部 -->
      <div
        class="flex items-center justify-between px-3 py-2 bg-gray-100 dark:bg-gray-800 cursor-move select-none border-b border-gray-200 dark:border-gray-700"
        @mousedown="startDrag"
      >
        <span class="text-xs font-medium text-gray-600 dark:text-gray-400">内部引用位置</span>
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
      <div class="p-3 space-y-2">
        <!-- 页面信息 -->
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-500 dark:text-gray-400">目标页面</span>
          <span class="text-sm font-medium text-blue-600 dark:text-blue-400">{{ positionText }}</span>
        </div>

        <!-- 坐标信息 -->
        <div class="space-y-1">
          <span class="text-xs text-gray-500 dark:text-gray-400">目标坐标 (PDF单位)</span>
          <div class="text-xs font-mono bg-gray-50 dark:bg-gray-800 px-2 py-1.5 rounded text-gray-700 dark:text-gray-300 break-all">
            {{ coordinateInfo }}
          </div>
        </div>

        <!-- 缩放信息 -->
        <div v-if="zoomText" class="flex items-center justify-between">
          <span class="text-xs text-gray-500 dark:text-gray-400">目标缩放</span>
          <span class="text-xs text-gray-700 dark:text-gray-300">{{ zoomText }}</span>
        </div>

        <!-- 操作按钮 -->
        <div class="pt-2 flex gap-2">
          <button
            @click="goToPage"
            class="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 rounded-md transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
            跳转
          </button>
          <button
            @click="closePopup"
            class="flex-1 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors"
          >
            关闭
          </button>
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
</style>
