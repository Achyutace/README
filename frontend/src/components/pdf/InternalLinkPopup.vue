<script setup lang="ts">
// ------------------------- 导入依赖与状态 -------------------------
import { ref, computed, watch, onUnmounted } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { clamp } from '@vueuse/core'

// 初始化 PDF store 实例
const pdfStore = usePdfStore()

// 拖拽相关状态
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const copied = ref(false)
const popupRef = ref<HTMLElement | null>(null)

// 从 store 获取数据
const isVisible = computed(() => pdfStore.internalLinkPopup.isVisible)
const position = computed(() => pdfStore.internalLinkPopup.position)
const linkData = computed(() => pdfStore.internalLinkPopup.linkData)
const isLoading = computed(() => pdfStore.internalLinkPopup.isLoading)
const error = computed(() => pdfStore.internalLinkPopup.error)

// 点击外部关闭弹窗的处理函数
function handleClickOutside(e: MouseEvent) {
  if (popupRef.value && !popupRef.value.contains(e.target as Node)) {
    closePopup()
  }
}

// 监听弹窗显示状态，只在显示时添加点击外部监听
watch(isVisible, (visible) => {
  if (visible) {
    // 弹窗显示时，延迟一点再添加监听，避免立即触发
    setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 0)
  } else {
    // 弹窗关闭时清理状态和监听
    isDragging.value = false
    copied.value = false
    document.removeEventListener('mousedown', handleClickOutside)
  }
})

// 组件卸载时确保移除监听
onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside)
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
  const clampedX = clamp(newX, 0, window.innerWidth - 420)
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

// 复制标题
async function copyTitle() {
  if (!linkData.value?.title) return
  try {
    await navigator.clipboard.writeText(linkData.value.title)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('复制失败:', err)
  }
}

// 跳转到 URL
function openUrl() {
  if (!linkData.value?.url) return
  window.open(linkData.value.url, '_blank')
}
</script>

<template>
  <Teleport to="body">
    <div
      ref="popupRef"
      v-if="isVisible"
      class="internal-link-popup fixed z-[9999] w-[400px] bg-white dark:bg-[#1e1e1e] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
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
      <div class="p-4 relative">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="flex items-center justify-center py-8">
          <div class="loading-spinner mr-2"></div>
          <span class="text-sm text-gray-500">加载中...</span>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="text-sm text-red-500 text-center py-4">
          {{ error }}
        </div>

        <!-- 论文信息卡片 -->
        <div v-else-if="linkData" class="relative pr-12">
          <!-- 标题行：标题 + 复制按钮 -->
          <div class="flex items-start gap-2 mb-2">
            <h3 class="text-base font-semibold text-blue-600 dark:text-blue-400 leading-tight flex-1">
              {{ linkData.title }}
            </h3>
            <button
              @click="copyTitle"
              class="flex-shrink-0 p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-full transition-all"
              :class="{ 'text-green-500 bg-green-50 dark:bg-green-900/20': copied }"
              :title="copied ? '已复制' : '复制标题'"
            >
              <svg v-if="!copied" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
            </button>
          </div>

          <!-- 作者 -->
          <div class="text-sm text-gray-600 dark:text-gray-400 mb-1.5">
            {{ linkData.authors?.join(', ') || '未知作者' }}
          </div>

          <!-- 来源 -->
          <div class="text-sm text-gray-500 dark:text-gray-500 mb-3">
            {{ linkData.source || '未知来源' }}
          </div>

          <!-- 概要 -->
          <div class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-4">
            {{ linkData.snippet || '暂无概要' }}
          </div>

          <!-- 右下角跳转按钮 -->
          <button
            @click="openUrl"
            class="absolute right-0 bottom-0 w-10 h-10 rounded-full bg-blue-500 hover:bg-blue-600 text-white flex items-center justify-center shadow-md hover:shadow-lg transition-all transform hover:scale-105"
            title="打开链接"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
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

/* 多行文本截断 */
.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
