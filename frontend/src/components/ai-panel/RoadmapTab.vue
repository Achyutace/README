<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'

const aiStore = useAiStore()
const libraryStore = useLibraryStore()
const { onNodeClick, fitView } = useVueFlow()

const selectedNode = ref<any>(null)

// Helper to fetch roadmap
async function loadRoadmap() {
  if (libraryStore.currentDocument) {
    await aiStore.fetchRoadmap(libraryStore.currentDocument.id)
  }
}

onMounted(() => {
  if (!aiStore.roadmap) {
    loadRoadmap()
  }
})

// Watch for document changes to reload roadmap
watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    // Reset selection when document changes
    selectedNode.value = null
    // If roadmap is already loaded for this ID (handled in store) or needs loading
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
  document.body.appendChild(downloadAnchorNode); // required for firefox
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
}

function closeDetail() {
  selectedNode.value = null
}
</script>

<template>
  <div class="h-full flex flex-col relative">
    <div class="px-4 py-3 border-b border-gray-200 flex justify-between items-center bg-white z-10">
      <div>
        <h3 class="text-sm font-medium text-gray-700">思维导图</h3>
        <p class="text-xs text-gray-500">点击节点查看相关细节</p>
      </div>
      <button 
        @click="exportRoadmap"
        class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded transition-colors"
        title="导出为 JSON"
      >
        Export
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="aiStore.isLoadingRoadmap" class="flex-1 flex items-center justify-center">
      <div class="flex flex-col items-center gap-2">
        <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
        <span class="text-sm text-gray-500">生成 Roadmap 中...</span>
      </div>
    </div>

    <!-- Roadmap View -->
    <div v-else-if="aiStore.roadmap" class="flex-1 w-full h-full relative">
      <VueFlow
        :nodes="aiStore.roadmap.nodes"
        :edges="aiStore.roadmap.edges"
        :class="{ 'dark': false }"
        class="basicflow"
        :default-viewport="{ zoom: 1.5 }"
        :min-zoom="0.2"
        :max-zoom="4"
        fit-view-on-init
      >
        <Background pattern-color="#aaa" :gap="8" />
        <Controls />
      </VueFlow>

      <!-- Detail Overlay -->
      <div 
        v-if="selectedNode" 
        class="absolute inset-x-0 bottom-0 bg-white border-t border-gray-200 shadow-lg transition-transform duration-300 transform p-4 max-h-[50%] overflow-y-auto"
      >
        <div class="flex justify-between items-start mb-2">
          <h4 class="font-bold text-gray-800">{{ selectedNode.label }}</h4>
          <button @click="closeDetail" class="text-gray-400 hover:text-gray-600">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <p class="text-sm text-gray-600 mb-3">{{ selectedNode.description }}</p>
        
        <div v-if="selectedNode.papers && selectedNode.papers.length > 0">
          <h5 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">相关论文 & 链接</h5>
          <ul class="space-y-2">
            <li v-for="(paper, idx) in selectedNode.papers" :key="idx" class="text-sm border-l-2 border-primary-200 pl-3">
              <a :href="paper.link" target="_blank" class="font-medium text-primary-600 hover:text-primary-800 hover:underline block truncate">
                {{ paper.title }}
              </a>
              <span class="text-xs text-gray-400">{{ paper.year || 'N/A' }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="flex-1 flex items-center justify-center p-8 text-center bg-gray-50">
      <p class="text-sm text-gray-500">暂无 Roadmap 数据<br>请选择文档开始分析</p>
    </div>
  </div>
</template>

<style>
/* modify some vue flow default styles if needed */
.vue-flow__node {
  font-size: 12px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  width: auto;
  text-align: center;
  cursor: pointer;
}

.vue-flow__node.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.vue-flow__handle {
  width: 6px;
  height: 6px;
  background: #bbb;
}
</style>
