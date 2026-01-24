<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const aiStore = useAiStore()
const libraryStore = useLibraryStore()
const { onNodeClick, fitView } = useVueFlow()

const selectedNode = ref<any>(null)

// --- 拖拽窗口逻辑 ---
const windowRef = ref<HTMLElement | null>(null)
const dragState = ref({
  isDragging: false,
  startX: 0,
  startY: 0,
  initialLeft: 0,
  initialTop: 0
})

// 初始位置：屏幕右上区域，避开工具栏
const position = ref({ x: window.innerWidth - 450, y: 120 })

function startDrag(event: MouseEvent) {
  if (!windowRef.value) return
  dragState.value.isDragging = true
  dragState.value.startX = event.clientX
  dragState.value.startY = event.clientY
  
  const rect = windowRef.value.getBoundingClientRect()
  dragState.value.initialLeft = rect.left
  dragState.value.initialTop = rect.top

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!dragState.value.isDragging) return
  const deltaX = event.clientX - dragState.value.startX
  const deltaY = event.clientY - dragState.value.startY
  
  position.value.x = dragState.value.initialLeft + deltaX
  position.value.y = dragState.value.initialTop + deltaY
}

function stopDrag() {
  dragState.value.isDragging = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
})
// --------------------

async function loadRoadmap() {
  if (libraryStore.currentDocument) {
    await aiStore.fetchRoadmap(libraryStore.currentDocument.id)
    setTimeout(() => fitView(), 100)
  }
}

onMounted(() => {
  if (!aiStore.roadmap) {
    loadRoadmap()
  }
})

watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    selectedNode.value = null
    loadRoadmap()
  }
})

onNodeClick((event) => {
  selectedNode.value = event.node.data
})

function exportRoadmap() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(aiStore.roadmap, null, 2));
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
    class="fixed z-[100] bg-white rounded-lg shadow-2xl border border-gray-300 flex flex-col resize overflow-hidden min-w-[300px] min-h-[250px]"
    :style="{
      left: `${position.x}px`,
      top: `${position.y}px`,
      width: '400px',  
      height: '350px' 
    }"
  >
    <!-- 头部：拖拽区域 & 工具栏 -->
    <div 
      class="h-9 bg-gray-100 border-b border-gray-200 flex justify-between items-center px-3 select-none"
      :class="dragState.isDragging ? 'cursor-grabbing' : 'cursor-grab'"
      @mousedown="startDrag"
    >
      <div class="flex items-center gap-2">
        <!-- Move Icon -->
        <svg class="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
        <span class="text-xs font-bold text-gray-700">Roadmap</span>
      </div>
      
      <div class="flex items-center gap-2" @mousedown.stop>
        <button 
          @click="exportRoadmap"
          class="text-[10px] bg-white hover:bg-gray-200 border border-gray-300 text-gray-600 px-1.5 py-0.5 rounded transition-colors"
          title="导出 JSON"
        >
          Export
        </button>
        <!-- 关闭按钮 -->
        <button 
          @click="$emit('close')"
          class="text-gray-400 hover:text-red-500 transition-colors p-0.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="flex-1 relative w-full h-full bg-gray-50 overflow-hidden">
      <!-- Loading -->
      <div v-if="aiStore.isLoadingRoadmap" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 z-10">
        <div class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mb-2"></div>
        <span class="text-xs text-gray-500">Generating...</span>
      </div>

      <!-- Flow Chart -->
      <VueFlow
        v-if="aiStore.roadmap"
        :nodes="aiStore.roadmap.nodes"
        :edges="aiStore.roadmap.edges"
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
      <div v-else-if="!aiStore.isLoadingRoadmap" class="absolute inset-0 flex items-center justify-center text-center p-4">
        <p class="text-xs text-gray-400">No Roadmap Data</p>
      </div>

      <!-- 详情弹层 (Overlay inside the box) -->
      <div 
        v-if="selectedNode" 
        class="absolute inset-x-0 bottom-0 top-1/2 bg-white/95 backdrop-blur-sm border-t border-gray-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] p-3 overflow-y-auto z-20"
      >
        <div class="flex justify-between items-start mb-1 sticky top-0 bg-white/95 pb-1">
          <h4 class="font-bold text-gray-800 text-xs truncate pr-2">{{ selectedNode.label }}</h4>
          <button @click="closeDetail" class="text-gray-400 hover:text-gray-600">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <p class="text-xs text-gray-600 mb-2 leading-relaxed">{{ selectedNode.description }}</p>
        
        <div v-if="selectedNode.papers && selectedNode.papers.length > 0">
          <ul class="space-y-1.5">
            <li v-for="(paper, idx) in selectedNode.papers" :key="idx" class="text-xs border-l-2 border-primary-300 pl-2">
              <a :href="paper.link" target="_blank" class="font-medium text-primary-600 hover:text-primary-800 hover:underline block truncate" :title="paper.title">
                {{ paper.title }}
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>
    
    <!-- 右下角 Resize Icon -->
    <div class="absolute bottom-0 right-0 w-3 h-3 pointer-events-none">
       <svg class="text-gray-400 w-full h-full" viewBox="0 0 24 24" fill="currentColor"><path d="M22 22H20V20H22V22ZM22 18H20V16H22V18ZM18 22H16V20H18V22ZM14 22H12V20H14V22Z" /></svg>
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

.resize::-webkit-scrollbar {
  display: none; 
}
</style>
