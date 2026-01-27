<script setup lang="ts">
// ------------------------- 导入依赖与子组件 -------------------------
// 引入 Vue 的响应式 API（ref、computed、watch），用于管理组件状态和响应式数据
import { ref, computed, watch } from 'vue'
// 引入 PDF store，用于管理 PDF 相关的状态和数据
import { usePdfStore } from '../../stores/pdf'
// 引入 NoteEditor 组件，用于渲染笔记内容
import NoteEditor from '../notes/NoteEditor.vue'

// 获取 PDF store 的实例，用于访问和修改 PDF 相关状态
const pdfStore = usePdfStore()

// 定义拖动相关的响应式状态变量
const isDragging = ref(false)  // 标记当前是否正在拖动卡片
const dragOffset = ref({ x: 0, y: 0 })  // 存储拖动时的鼠标偏移量，用于计算新位置

// 从 PDF store 中获取计算属性，用于响应式地获取卡片的可见性、笔记数据和位置
const isVisible = computed(() => pdfStore.notePreviewCard.isVisible)  // 卡片是否可见
const note = computed(() => pdfStore.notePreviewCard.note)  // 当前预览的笔记对象
const position = computed(() => pdfStore.notePreviewCard.position)  // 卡片在屏幕上的位置

// 拖动开始函数，当用户按下鼠标时触发
function startDrag(e: MouseEvent) {
  isDragging.value = true  // 设置拖动状态为 true
  // 计算鼠标按下时的偏移量，用于后续拖动计算
  dragOffset.value = {
    x: e.clientX - position.value.x,  // 鼠标 X 坐标减去卡片当前位置 X
    y: e.clientY - position.value.y   // 鼠标 Y 坐标减去卡片当前位置 Y
  }
  // 添加全局鼠标移动和鼠标释放事件监听器
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()  // 阻止默认事件，如文本选择
}

// 拖动过程中函数，当鼠标移动时触发
function onDrag(e: MouseEvent) {
  if (!isDragging.value) return  // 如果没有在拖动状态，直接返回
  // 计算新的卡片位置
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  // 限制卡片位置在视口内，避免拖出屏幕
  const clampedX = Math.max(0, Math.min(window.innerWidth - 320, newX))  // 320 是卡片宽度
  const clampedY = Math.max(0, Math.min(window.innerHeight - 100, newY))  // 100 是底部边距
  // 更新 PDF store 中的卡片位置
  pdfStore.updateNotePreviewPosition({ x: clampedX, y: clampedY })
}

// 拖动结束函数，当鼠标释放时触发
function stopDrag() {
  isDragging.value = false  // 重置拖动状态
  // 移除全局事件监听器，清理资源
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭卡片函数，隐藏笔记预览卡片
function closeCard() {
  pdfStore.closeNotePreviewCard()  // 调用 store 方法关闭卡片
}

// 监听卡片可见性变化，用于组件卸载时的清理工作
watch(isVisible, (visible) => {
  if (!visible) {  // 当卡片变为不可见时
    // 移除事件监听器，防止内存泄漏
    document.removeEventListener('mousemove', onDrag)
    document.removeEventListener('mouseup', stopDrag)
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isVisible && note"
      class="note-preview-card fixed z-[9999] w-[320px] bg-white dark:bg-[#1e1e1e] rounded-xl shadow-2xl border border-amber-200 dark:border-amber-800 overflow-hidden"
      :style="{ left: position.x + 'px', top: position.y + 'px' }"
    >
      <!-- 拖动头部 -->
      <div
        class="flex items-center justify-between px-4 py-2 bg-amber-50 dark:bg-amber-900/30 cursor-move select-none border-b border-amber-100 dark:border-amber-800"
        @mousedown="startDrag"
      >
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-xs font-medium text-amber-700 dark:text-amber-400">笔记预览</span>
        </div>
        <button
          @click="closeCard"
          class="p-1 hover:bg-amber-100 dark:hover:bg-amber-800 rounded-full transition-colors"
        >
          <svg class="w-4 h-4 text-amber-500 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- 内容区域 -->
      <div class="p-4 max-h-[350px] overflow-y-auto">
        <!-- 标题 -->
        <h3 class="text-base font-semibold text-amber-700 dark:text-amber-400 mb-3 leading-snug">
          {{ note.title || '无标题' }}
        </h3>

        <!-- 内容 (使用 NoteEditor 渲染 Markdown) -->
        <div class="note-content text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          <NoteEditor
            v-if="note.content"
            :model-value="note.content"
            :editable="false"
          />
          <p v-else class="text-gray-400 dark:text-gray-500 italic">暂无内容</p>
        </div>
      </div>

      <!-- 底部提示 -->
      <div class="px-4 py-2 bg-gray-50 dark:bg-[#252525] border-t border-gray-100 dark:border-gray-700">
        <p class="text-[10px] text-gray-400 dark:text-gray-500">
          Ctrl + 点击词语可快速查看相关笔记
        </p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.note-preview-card {
  animation: slideIn 0.2s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 笔记内容样式 */
.note-content :deep(.markdown-content) {
  @apply text-sm text-gray-600 dark:text-gray-400;
}

.note-content :deep(.markdown-content h1),
.note-content :deep(.markdown-content h2),
.note-content :deep(.markdown-content h3) {
  @apply font-semibold text-gray-800 dark:text-gray-200 mt-2 mb-1;
}

.note-content :deep(.markdown-content p) {
  @apply my-1 leading-relaxed;
}

.note-content :deep(.markdown-content ul),
.note-content :deep(.markdown-content ol) {
  @apply pl-4 my-1;
}

.note-content :deep(.markdown-content code) {
  @apply px-1 py-0.5 bg-gray-100 dark:bg-gray-700 text-xs rounded font-mono text-pink-500;
}

.note-content :deep(.markdown-content blockquote) {
  @apply border-l-2 border-amber-300 dark:border-amber-600 pl-2 my-2 text-gray-500 italic;
}
</style>
