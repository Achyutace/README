<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'

// Props for panel states
const props = defineProps<{
  notesMinimized?: boolean
  chatMinimized?: boolean
}>()

// Emits for panel toggle
const emit = defineEmits<{
  (e: 'toggle-notes'): void
  (e: 'toggle-chat'): void
}>()

const pdfStore = usePdfStore()
const aiStore = useAiStore()
const libraryStore = useLibraryStore()
const pageInput = ref('')
const scaleInput = ref(String(pdfStore.scalePercent))
const showRoadmap = ref(false)
const selectedNode = ref<any>(null)

const { onNodeClick } = useVueFlow()

async function loadRoadmap() {
  if (libraryStore.currentDocument) {
    await aiStore.fetchRoadmap(libraryStore.currentDocument.id)
  }
}

onNodeClick((event) => {
  selectedNode.value = event.node.data
})

function closeDetail() {
  selectedNode.value = null
}

function closeRoadmap() {
  showRoadmap.value = false
  selectedNode.value = null
}

function exportRoadmap() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(aiStore.roadmap, null, 2));
  const downloadAnchorNode = document.createElement('a');
  downloadAnchorNode.setAttribute("href", dataStr);
  downloadAnchorNode.setAttribute("download", "roadmap.json");
  document.body.appendChild(downloadAnchorNode);
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
}

watch(showRoadmap, (val) => {
  if (val && !aiStore.roadmap) {
    loadRoadmap()
  }
})

function handlePageInput() {
  const page = parseInt(pageInput.value)
  if (!isNaN(page)) {
    pdfStore.goToPage(page)
  }
  pageInput.value = ''
}

function applyScaleInput() {
  const value = parseFloat(scaleInput.value)
  if (isNaN(value)) {
    scaleInput.value = String(pdfStore.scalePercent)
    return
  }
  pdfStore.setScale(value / 100)
  scaleInput.value = String(pdfStore.scalePercent)
}

watch(
  () => pdfStore.scalePercent,
  (val) => {
    scaleInput.value = String(val)
  }
)
</script>

<template>
  <div class="relative">
    <div class="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
      <!-- Left: Zoom Controls -->
      <div class="flex items-center gap-2">
        <button
          @click="pdfStore.zoomOut"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="缩小"
        >
          <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
          </svg>
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model="scaleInput"
            type="number"
            min="50"
            max="300"
            step="1"
            @keyup.enter="applyScaleInput"
            @blur="applyScaleInput"
            class="w-16 px-2 py-1 text-center text-sm border border-gray-300 rounded focus:outline-none focus:border-primary-500 no-spinner"
          />
          <span class="text-sm text-gray-600">%</span>
        </div>
        <button
          @click="pdfStore.zoomIn"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="放大"
        >
          <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <!-- Center: Page Navigation -->
      <div class="flex items-center gap-2">
        <button
          @click="pdfStore.prevPage"
          :disabled="pdfStore.currentPage <= 1"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="上一页"
        >
          <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <div class="flex items-center gap-1">
          <input
            v-model="pageInput"
            type="text"
            :placeholder="String(pdfStore.currentPage)"
            @keyup.enter="handlePageInput"
            class="w-12 px-2 py-1 text-center text-sm border border-gray-300 rounded focus:outline-none focus:border-primary-500"
          />
          <span class="text-sm text-gray-500">/</span>
          <span class="text-sm text-gray-700">{{ pdfStore.totalPages || '-' }}</span>
        </div>

        <button
          @click="pdfStore.nextPage"
          :disabled="pdfStore.currentPage >= pdfStore.totalPages"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="下一页"
        >
          <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <!-- Right: Roadmap Button + Panel Toggles -->
      <div class="flex items-center gap-1">
        <button
          @click="showRoadmap = !showRoadmap"
          :class="[
            'px-3 py-1.5 text-sm rounded-lg transition-colors',
            showRoadmap
              ? 'bg-primary-100 text-primary-700'
              : 'hover:bg-gray-100 text-gray-600'
          ]"
          title="思维导图"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
            </svg>
            Roadmap
          </span>
        </button>

        <!-- Divider -->
        <div class="w-px h-6 bg-gray-300 mx-1"></div>

        <!-- Notes Panel Toggle -->
        <button
          @click="emit('toggle-notes')"
          :class="[
            'px-2 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.notesMinimized
              ? 'bg-gray-100 text-gray-500'
              : 'hover:bg-gray-100 text-gray-600'
          ]"
          :title="props.notesMinimized ? '展开笔记' : '收起笔记'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-xs">笔记</span>
        </button>

        <!-- Chat Panel Toggle -->
        <button
          @click="emit('toggle-chat')"
          :class="[
            'px-2 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.chatMinimized
              ? 'bg-gray-100 text-gray-500'
              : 'hover:bg-gray-100 text-gray-600'
          ]"
          :title="props.chatMinimized ? '展开对话' : '收起对话'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <span class="text-xs">对话</span>
        </button>

        <!-- Divider -->
        <div class="w-px h-6 bg-gray-300 mx-1"></div>

        <!-- Collapse All Panels Button -->
        <button
          @click="aiStore.isPanelCollapsed = !aiStore.isPanelCollapsed"
          :class="[
            'p-1.5 rounded-lg transition-colors',
            aiStore.isPanelCollapsed
              ? 'bg-primary-100 text-primary-600'
              : 'hover:bg-gray-100 text-gray-600'
          ]"
          :title="aiStore.isPanelCollapsed ? '展开侧边栏' : '收起侧边栏'"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              :d="aiStore.isPanelCollapsed
                ? 'M11 19l-7-7 7-7m8 14l-7-7 7-7'
                : 'M13 5l7 7-7 7M5 5l7 7-7 7'"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Roadmap Popup - Centered over PDF -->
    <div
      v-if="showRoadmap"
      class="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[550px] bg-white rounded-lg shadow-2xl border border-gray-200 z-[9999] flex flex-col overflow-hidden"
    >
      <!-- Popup Header -->
      <div class="px-4 py-3 border-b border-gray-200 flex justify-between items-center bg-gray-50">
        <div>
          <h3 class="text-sm font-medium text-gray-700">思维导图</h3>
          <p class="text-xs text-gray-500">点击节点查看相关细节</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="exportRoadmap"
            class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded transition-colors"
            title="导出为 JSON"
          >
            Export
          </button>
          <button
            @click="closeRoadmap"
            class="text-gray-400 hover:text-gray-600 p-1"
            title="关闭"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Popup Content -->
      <div class="flex-1 relative">
        <!-- Loading State -->
        <div v-if="aiStore.isLoadingRoadmap" class="absolute inset-0 flex items-center justify-center">
          <div class="flex flex-col items-center gap-2">
            <div class="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            <span class="text-sm text-gray-500">生成 Roadmap 中...</span>
          </div>
        </div>

        <!-- Roadmap Display -->
        <div v-else-if="aiStore.roadmap" class="w-full h-full">
          <VueFlow
            :nodes="aiStore.roadmap.nodes"
            :edges="aiStore.roadmap.edges"
            class="basicflow"
            :default-viewport="{ zoom: 1.2 }"
            :min-zoom="0.2"
            :max-zoom="4"
            fit-view-on-init
          >
            <Background pattern-color="#aaa" :gap="8" />
            <Controls />
          </VueFlow>

          <!-- Node Detail Panel -->
          <div
            v-if="selectedNode"
            class="absolute inset-x-0 bottom-0 bg-white border-t border-gray-200 shadow-lg p-4 max-h-[40%] overflow-y-auto"
          >
            <div class="flex justify-between items-start mb-2">
              <h4 class="font-bold text-gray-800">{{ selectedNode.label }}</h4>
              <button @click="closeDetail" class="text-gray-400 hover:text-gray-600">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
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
        <div v-else class="absolute inset-0 flex items-center justify-center p-8 text-center bg-gray-50">
          <p class="text-sm text-gray-500">暂无 Roadmap 数据<br>请选择文档开始分析</p>
        </div>
      </div>
    </div>

    <!-- Backdrop -->
    <div
      v-if="showRoadmap"
      class="fixed inset-0 z-[9998] bg-black/30"
      @click="closeRoadmap"
    ></div>
  </div>
</template>

<style>
.no-spinner::-webkit-outer-spin-button,
.no-spinner::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.no-spinner[type='number'] {
  -moz-appearance: textfield;
}

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
