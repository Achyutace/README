<script setup lang="ts">
/*
----------------------------------------------------------------------
                            Roadmap 组件
----------------------------------------------------------------------
*/ 

// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、VueFlow 相关组件以及所需的 store
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useRoadmapStore } from '../../stores/roadmap'
import { useLibraryStore } from '../../stores/library'

const emit = defineEmits<{
  (e: 'close'): void
}>()

// ------------------------- 初始化 store 实例 -------------------------
// 组合式 store 实例用于访问应用级状态和 VueFlow 辅助函数
const roadmapStore = useRoadmapStore()
const libraryStore = useLibraryStore()
const { onNodeClick, fitView } = useVueFlow()

const selectedNode = ref<any>(null)

// ------------------------- 拖拽窗口逻辑 -------------------------
// 窗口引用
const windowRef = ref<HTMLElement | null>(null)

// 拖拽状态
const dragState = ref({
  isDragging: false,
  startX: 0,
  startY: 0,
  initialLeft: 0,
  initialTop: 0
})

// 初始位置：屏幕右上区域，避开工具栏
const position = ref({ x: window.innerWidth - 450, y: 120 })

// 拖拽处理函数
function startDrag(event: MouseEvent) {
  // 确保窗口存在
  if (!windowRef.value) return

  // 初始化拖拽状态
  dragState.value.isDragging = true
  dragState.value.startX = event.clientX
  dragState.value.startY = event.clientY
  
  // 获取窗口当前位置信息
  const rect = windowRef.value.getBoundingClientRect()
  dragState.value.initialLeft = rect.left
  dragState.value.initialTop = rect.top

  // 监听全局鼠标移动和释放事件
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

// 拖拽过程中更新位置
function onDrag(event: MouseEvent) {
  // 保证正在拖拽
  if (!dragState.value.isDragging) return

  // 计算位置偏移
  const deltaX = event.clientX - dragState.value.startX
  const deltaY = event.clientY - dragState.value.startY
  
  // 更新窗口位置
  position.value.x = dragState.value.initialLeft + deltaX
  position.value.y = dragState.value.initialTop + deltaY
}

// 停止拖拽
function stopDrag() {
  // 重置拖拽状态
  dragState.value.isDragging = false

  // 移除全局事件监听
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

// ------------------------- Roadmap 加载与生命周期 -------------------------
// 负责从 AI store 拉取 roadmap 数据并在视图上自适应
async function loadRoadmap() {
  // 确保有当前文档
  if (libraryStore.currentDocument) {
    // 拉取 roadmap 数据（见 ai.ts）
    await roadmapStore.fetchRoadmap(libraryStore.currentDocument.id) 
    // 100ms 后超时，加载默认页面
    setTimeout(() => fitView(), 100)
  } else {
    console.warn('Cannot load roadmap: no current document selected')
  }
}

// 监听当前文档变化，重新加载 roadmap
watch(() => libraryStore.currentDocument?.id, (newId) => {
  
  if (newId) {
    selectedNode.value = null
    loadRoadmap()
  } else {
    console.warn('Current document cleared, roadmap will not be loaded')
  }
})

// 监听节点点击事件，显示节点详情
onNodeClick((event) => {
  selectedNode.value = event.node.data
})

// ------------------------- 导出与交互函数 -------------------------
// 导出 roadmap 为 JSON，及关闭节点详情的辅助函数
function exportRoadmap() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(roadmapStore.roadmap, null, 2));
  const downloadAnchorNode = document.createElement('a');
  downloadAnchorNode.setAttribute("href", dataStr);
  downloadAnchorNode.setAttribute("download", "roadmap.json");
  document.body.appendChild(downloadAnchorNode);
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
}

function closeDetail() {
  selectedNode.value = null
}

onMounted(() => {
  if (!roadmapStore.roadmap) {
    loadRoadmap()
  }
})

// 防御性移除：组件卸载时确保事件监听被清理
onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
})

// ------------------------- 组件脚本结束 -------------------------
// ---------------------------------------------------------------


// ------------------------- 组件模板开始 -------------------------
// （以下内容可以在 F12 开发者工具中查看）
</script>

<template>
  <!-- 
    主要样式调整：
    1. fixed 定位
    2. z-[100] 保证最上层
    3. shadow-2xl 和 border 增强弹窗感
  -->
  <div
    ref="windowRef"
    class="fixed z-[100] bg-white dark:bg-[#1e1e1e] rounded-lg shadow-2xl border border-gray-300 dark:border-gray-700 flex flex-col resize overflow-hidden min-w-[300px] min-h-[250px]"
    :style="{
      left: `${position.x}px`,
      top: `${position.y}px`,
      width: '400px',
      height: '350px'
    }"
  >
    <!-- 头部：拖拽区域 & 工具栏 -->
    <div
      class="h-9 bg-gray-100 dark:bg-[#2d2d30] border-b border-gray-200 dark:border-gray-700 flex justify-between items-center px-3 select-none"
      :class="dragState.isDragging ? 'cursor-grabbing' : 'cursor-grab'"
      @mousedown="startDrag"
    >
      <div class="flex items-center gap-2">
        <!-- Move Icon -->
        <svg class="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
        <span class="text-xs font-bold text-gray-700 dark:text-gray-300">Roadmap</span>
      </div>

      <div class="flex items-center gap-2" @mousedown.stop>
        <button
          @click="exportRoadmap"
          class="text-[10px] bg-white dark:bg-[#3e3e42] hover:bg-gray-200 dark:hover:bg-[#4e4e52] border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded transition-colors"
          title="导出 JSON"
        >
          Export
        </button>
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 transition-colors p-0.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="flex-1 relative w-full h-full bg-gray-50 dark:bg-[#252526] overflow-hidden">
      <!-- Loading -->
      <div v-if="roadmapStore.isLoadingRoadmap" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-[#1e1e1e]/80 z-10">
        <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mb-2"></div>
        <span class="text-xs text-gray-500 dark:text-gray-400">Generating...</span>
      </div>

      <!-- Flow Chart -->
      <VueFlow
        v-if="roadmapStore.roadmap"
        :nodes="roadmapStore.roadmap.nodes"
        :edges="roadmapStore.roadmap.edges"
        class="basicflow w-full h-full"
        :default-viewport="{ zoom: 1 }"
        :min-zoom="0.2"
        :max-zoom="4"
        fit-view-on-init
      >
        <Background pattern-color="#ddd" :gap="12" :size="1" />
        <Controls position="bottom-left" class="scale-75 origin-bottom-left" />
      </VueFlow>

      <!-- Empty State -->
      <div v-else-if="!roadmapStore.isLoadingRoadmap" class="absolute inset-0 flex items-center justify-center text-center p-4">
        <p class="text-xs text-gray-400 dark:text-gray-500">No Roadmap Data</p>
      </div>

      <!-- 详情弹层 (Overlay inside the box) -->
      <div
        v-if="selectedNode"
        class="absolute inset-x-0 bottom-0 top-1/2 bg-white/95 dark:bg-[#2d2d30]/95 backdrop-blur-sm border-t border-gray-200 dark:border-gray-700 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] p-3 overflow-y-auto z-20"
      >
        <div class="flex justify-between items-start mb-1 sticky top-0 bg-white/95 dark:bg-[#2d2d30]/95 pb-1">
          <h4 class="font-bold text-gray-800 dark:text-gray-200 text-xs truncate pr-2">{{ selectedNode.label }}</h4>
          <button @click="closeDetail" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <p class="text-xs text-gray-600 dark:text-gray-400 mb-2 leading-relaxed">{{ selectedNode.description }}</p>

        <div v-if="selectedNode.papers && selectedNode.papers.length > 0">
          <ul class="space-y-1.5">
            <li v-for="(paper, idx) in selectedNode.papers" :key="idx" class="text-xs border-l-2 border-primary-300 dark:border-primary-600 pl-2">
              <a :href="paper.link" target="_blank" class="font-medium text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-300 hover:underline block truncate" :title="paper.title">
                {{ paper.title }}
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 右下角 Resize Icon -->
    <div class="absolute bottom-0 right-0 w-3 h-3 pointer-events-none">
       <svg class="text-gray-400 dark:text-gray-600 w-full h-full" viewBox="0 0 24 24" fill="currentColor"><path d="M22 22H20V20H22V22ZM22 18H20V16H22V18ZM18 22H16V20H18V22ZM14 22H12V20H14V22Z" /></svg>
    </div>
  </div>
</template>

<style scoped>
:deep(.vue-flow__node) {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  width: auto;
  max-width: 120px;
  background: white;
  border: 1px solid #ddd;
  text-align: center;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

:deep(.vue-flow__node.selected) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.5);
}

/* Dark mode styles for VueFlow */
:global(.dark) :deep(.vue-flow__node) {
  background: #2d2d30;
  border-color: #4a4a4a;
  color: #e0e0e0;
}

:global(.dark) :deep(.vue-flow__node.selected) {
  border-color: #60a5fa;
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.5);
}

:global(.dark) :deep(.vue-flow__edge-path) {
  stroke: #6b7280;
}

:global(.dark) :deep(.vue-flow__controls) {
  background: #2d2d30;
  border-color: #4a4a4a;
}

:global(.dark) :deep(.vue-flow__controls-button) {
  background: #3e3e42;
  border-color: #4a4a4a;
  fill: #e0e0e0;
}

:global(.dark) :deep(.vue-flow__controls-button:hover) {
  background: #4e4e52;
}

.resize::-webkit-scrollbar {
  display: none;
}
</style>
