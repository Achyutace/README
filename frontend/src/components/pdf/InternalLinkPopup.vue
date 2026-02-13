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
const position = computed(() => pdfStore.internalLinkPopup.position)
const linkData = computed(() => pdfStore.internalLinkPopup.linkData)
const isLoading = computed(() => pdfStore.internalLinkPopup.isLoading)
const error = computed(() => pdfStore.internalLinkPopup.error)

// 格式化的 JSON 数据
const formattedJson = computed(() => {
  if (!linkData.value) return ''
  return JSON.stringify(linkData.value, null, 2)
})

// 关闭弹窗时清理
watch(isVisible, (visible) => {
  if (!visible) {
    isDragging.value = false
  }
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
  const clampedX = clamp(newX, 0, window.innerWidth - 380)
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
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="internal-link-popup fixed z-[9999] w-[380px] bg-white dark:bg-[#1e1e1e] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
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
      <div class="p-3">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="flex items-center justify-center py-8">
          <div class="loading-spinner mr-2"></div>
          <span class="text-sm text-gray-500">加载中...</span>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="text-sm text-red-500 text-center py-4">
          {{ error }}
        </div>

        <!-- JSON 数据展示 -->
        <div v-else-if="linkData" class="bg-gray-900 rounded overflow-hidden">
          <pre class="text-xs text-green-400 p-3 overflow-x-auto whitespace-pre-wrap break-all font-mono leading-relaxed">{{ formattedJson }}</pre>
        </div>

        <!-- 无数据状态 -->
        <div v-else class="text-sm text-gray-400 text-center py-4">
          暂无数据
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

/* 加载动画 */
.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e5e7eb;
  border-top-color: #6b7280;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 4px;
  height: 4px;
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
