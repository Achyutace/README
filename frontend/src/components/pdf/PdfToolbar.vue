<script setup lang="ts">
// ------------------------- 导入依赖与组件 -------------------------
// 从 Vue 导入响应式 API，和当前组件所需的 store/子组件
import { ref, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
// 1. 引入组件 (请确保 RoadmapTab.vue 文件存在于同级目录)
import RoadmapTab from '../roadmap/RoadmapTab.vue'

const props = defineProps<{
  notesVisible?: boolean
  chatVisible?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-notes-visibility'): void
  (e: 'toggle-chat-visibility'): void
}>()

const pdfStore = usePdfStore()
const pageInput = ref('')
const scaleInput = ref(String(pdfStore.scalePercent))
// 控制 Roadmap 显示的状态
const showRoadmap = ref(false)

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
  pdfStore.setScale((value / 100) * 1.5)
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
    <div class="flex items-center justify-between px-4 py-1.5 bg-white dark:bg-[#252526] border-b border-gray-200 dark:border-gray-800 shadow-sm">
      <!-- Left: Zoom Controls -->
      <div class="flex items-center gap-1.5">
        <button @click="pdfStore.zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title="缩小">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" /></svg>
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model="scaleInput"
            type="number"
            min="50" max="300" step="1"
            @keyup.enter="applyScaleInput" @blur="applyScaleInput"
            class="w-14 px-2 py-0.5 text-center text-sm border border-gray-300 dark:border-gray-600 dark:bg-[#3e3e42] dark:text-gray-200 rounded focus:outline-none focus:border-primary-500 dark:focus:border-primary-400 no-spinner"
          />
          <span class="text-sm text-gray-600 dark:text-gray-400">%</span>
        </div>
        <button @click="pdfStore.zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title="放大">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        </button>
      </div>

      <!-- Center: Page Navigation -->
      <div class="flex items-center gap-1.5">
        <button @click="pdfStore.prevPage" :disabled="pdfStore.currentPage <= 1" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed" title="上一页">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model="pageInput"
            type="text"
            :placeholder="String(pdfStore.currentPage)"
            @keyup.enter="handlePageInput"
            class="w-10 px-2 py-0.5 text-center text-sm border border-gray-300 dark:border-gray-600 dark:bg-[#3e3e42] dark:text-gray-200 rounded focus:outline-none focus:border-primary-500 dark:focus:border-primary-400"
          />
          <span class="text-sm text-gray-500 dark:text-gray-400">/</span>
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ pdfStore.totalPages || '-' }}</span>
        </div>
        <button @click="pdfStore.nextPage" :disabled="pdfStore.currentPage >= pdfStore.totalPages" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed" title="下一页">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        </button>
      </div>

      <!-- Right: Roadmap Button + Panel Toggles -->
      <div class="flex items-center gap-1">
        <button
          @click="showRoadmap = !showRoadmap"
          :class="[
            'px-2.5 py-1 text-sm rounded-lg transition-colors',
            showRoadmap
              ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          title="思维导图"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" /></svg>
            Roadmap
          </span>
        </button>

        <!-- 分割线 -->
        <div class="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1"></div>

        <!-- 笔记开关 -->
        <button
          @click="emit('toggle-notes-visibility')"
          :class="[
            'px-2 py-1 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.notesVisible
              ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          :title="props.notesVisible ? '隐藏笔记' : '显示笔记'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </button>

        <!-- 对话开关 -->
        <button
          @click="emit('toggle-chat-visibility')"
          :class="[
            'px-2 py-1 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.chatVisible
              ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          :title="props.chatVisible ? '隐藏对话' : '显示对话'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 2. 使用 Teleport 将窗口渲染到 body，确保可见且不被遮挡 -->
    <Teleport to="body">
      <RoadmapTab 
        v-if="showRoadmap" 
        @close="showRoadmap = false" 
      />
    </Teleport>
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
</style>
