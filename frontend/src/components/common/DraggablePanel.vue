<script setup lang="ts">
// 可拖拽 & 可缩放 面板组件（DraggablePanel）
// 说明：此组件将拖拽与缩放逻辑抽象到 composables 中（useDraggableWindow、useResizableWindow），
// 并对外暴露了 position/size 的双向绑定事件和一些钩子事件（drag-start、drag-end 等）。

import { watch } from 'vue'
import { useDraggableWindow, type Position } from '../../composables/useDraggableWindow'
import { useResizableWindow, type Size, type ResizeEvent } from '../../composables/useResizableWindow'

// Props：组件对外可配置的一些参数
const props = defineProps<{
  // 面板标题（可选）
  title?: string
  // 初始位置（x, y），用于“受控”模式或初始化位置
  initialPosition?: Position
  // 初始大小（width, height），用于“受控”模式或初始化大小
  initialSize?: Size
  // 最小/最大 宽高（用于缩放限制）
  minWidth?: number
  minHeight?: number
  maxWidth?: number
  maxHeight?: number
  // 自定义 header 的 class（用于个性化头部样式）
  headerClass?: string
}>()

// Emits：组件向外触发的事件（父组件可以监听）
const emit = defineEmits<{
  (e: 'close'): void
  // 当拖动或外部更新位置时触发（双向绑定用）
  (e: 'update:position', pos: Position): void
  // 当缩放或外部更新大小时触发（双向绑定用）
  (e: 'update:size', size: Size): void
  (e: 'drag-start'): void
  (e: 'drag-end', pos: Position): void
}>()

// --- 拖拽逻辑 ---
// 使用 useDraggableWindow 提供 position、startDrag、isDragging
// - initialPosition: 初始位置
// - boundary: 限制拖拽范围（这里使用 window）
// - onDragStart/onDragEnd/onDrag: 对外派发相应事件
const { position, isDragging, startDrag } = useDraggableWindow({
  initialPosition: props.initialPosition,
  boundary: window,
  onDragStart: () => emit('drag-start'),
  onDragEnd: (pos) => emit('drag-end', pos),
  onDrag: (pos) => emit('update:position', pos)
})

// --- 缩放逻辑 ---
// 使用 useResizableWindow 提供 size、startResize、isResizing
// - initialSize: 初始大小
// - minWidth/minHeight/maxWidth/maxHeight: 缩放约束
// - onResize: 缩放过程中触发，含新大小和位移增量（delta）信息
const { size, startResize, isResizing } = useResizableWindow({
  initialSize: props.initialSize,
  minWidth: props.minWidth,
  minHeight: props.minHeight,
  maxWidth: props.maxWidth,
  maxHeight: props.maxHeight,
  onResize: (e: ResizeEvent) => {
    // 如果向左或向上缩放（delta.x/delta.y 非 0），需要同时调整 position
    // 例如：向左缩小时，宽度变小但面板的 x 需要向左移动 delta.x
    if (e.delta.x !== 0 || e.delta.y !== 0) {
      position.value = {
        x: position.value.x + e.delta.x,
        y: position.value.y + e.delta.y
      }
      // 同步派发 update:position，保持外部与内部的一致性
      emit('update:position', position.value)
    }
    // 派发当前大小，供外部同步或受控使用
    emit('update:size', e.size)
  }
})

// --- 响应外部 props 变化（可选） ---
// 当父组件以受控方式传入 initialPosition/initialSize 并更新时，
// 本组件会在不处于拖拽/缩放时同步这些值到内部状态，避免覆盖正在进行的交互。
watch(() => props.initialPosition, (newPos) => {
  if (newPos && !isDragging.value) {
    position.value = { ...newPos }
  }
}, { deep: true })

watch(() => props.initialSize, (newSize) => {
  if (newSize && !isResizing.value) {
    size.value = { ...newSize }
  }
}, { deep: true })

</script>

<template>
  <!-- 根节点：通过 inline style 受控 left/top/width/height 来定位与设置大小 -->
  <div
    class="draggable-panel fixed z-[1000] bg-white dark:bg-[#2d2d30] rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col"
    :class="{ 'is-dragging': isDragging, 'is-resizing': isResizing }"
    :style="{
      left: position.x + 'px',
      top: position.y + 'px',
      width: size.width + 'px',
      height: size.height + 'px',
    }"
  >
    <!-- 头部：可拖拽区域，绑定 mousedown 启动拖拽 -->
    <div 
      class="panel-header flex items-center justify-between px-3 py-2 select-none cursor-move"
      :class="headerClass || 'bg-gradient-to-r from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700 text-white'"
      @mousedown="startDrag"
    >
      <div class="flex items-center gap-2 overflow-hidden">
        <!-- 可插入自定义图标（slot） -->
        <slot name="icon">
           <!-- 默认图标（若未传入 icon slot 则显示此 SVG） -->
           <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7" /></svg>
        </slot>
        <!-- 标题，超过部分截断 -->
        <span class="text-sm font-medium truncate">{{ title || 'Panel' }}</span>
      </div>
      
      <div class="flex items-center gap-1 shrink-0" @mousedown.stop><!-- @mousedown.stop 防止点击头部操作影响拖拽开始 -->
        <!-- 头部操作区插槽（例如按钮） -->
        <slot name="header-actions"></slot>
        
        <!-- 关闭按钮：触发 close 事件 -->
        <button
          @click="emit('close')"
          class="p-1 hover:bg-white/20 rounded transition-colors"
          title="关闭"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
    
    <!-- 内容区：默认 slot，用于放置面板内容 -->
    <div class="panel-content flex-1 overflow-auto relative">
       <slot></slot>
    </div>
    
    <!-- 可选 Footer 区域：通过具名 slot footer 提供 -->
    <div v-if="$slots.footer" class="panel-footer px-3 py-1.5 bg-gray-50 dark:bg-[#252526] border-t border-gray-100 dark:border-gray-700">
      <slot name="footer"></slot>
    </div>

    <!-- 缩放手柄：用于不同方向的缩放，绑定 startResize 并传入方向参数 -->
    <div class="resize-handle resize-w" @mousedown="startResize($event, 'w')"></div>
    <div class="resize-handle resize-e" @mousedown="startResize($event, 'e')"></div>
    <div class="resize-handle resize-n" @mousedown="startResize($event, 'n')"></div>
    <div class="resize-handle resize-s" @mousedown="startResize($event, 's')"></div>
    <div class="resize-handle resize-sw" @mousedown="startResize($event, 'sw')"></div>
    <div class="resize-handle resize-se" @mousedown="startResize($event, 'se')"></div>
    <div class="resize-handle resize-nw" @mousedown="startResize($event, 'nw')"></div>
    <div class="resize-handle resize-ne" @mousedown="startResize($event, 'ne')"></div>
  </div>
</template>

<style scoped>
/* 主容器样式：阴影、模糊背景、圆角等 */
.draggable-panel {
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15), 0 8px 16px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(12px);
  /* 确保背景不完全透明以便内容可读 */
}

/* 内容区自定义滚动条：美观且与暗色模式兼容 */
.panel-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
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

/* 缩放手柄样式：透明但 hover 时高亮，便于用户发现 */
.resize-handle {
  position: absolute;
  background: transparent;
  z-index: 10;
}
.resize-handle:hover {
  background: rgba(59, 130, 246, 0.1);
}

/* 各方向手柄的定位与光标提示 */
.resize-w { left: 0; top: 10px; bottom: 10px; width: 6px; cursor: ew-resize; }
.resize-e { right: 0; top: 10px; bottom: 10px; width: 6px; cursor: ew-resize; }
.resize-n { top: 0; left: 10px; right: 10px; height: 6px; cursor: ns-resize; }
.resize-s { bottom: 0; left: 10px; right: 10px; height: 6px; cursor: ns-resize; }

.resize-nw { left: 0; top: 0; width: 12px; height: 12px; cursor: nwse-resize; }
.resize-ne { right: 0; top: 0; width: 12px; height: 12px; cursor: nesw-resize; }
.resize-sw { left: 0; bottom: 0; width: 12px; height: 12px; cursor: nesw-resize; }
.resize-se { right: 0; bottom: 0; width: 12px; height: 12px; cursor: nwse-resize; }
</style>
