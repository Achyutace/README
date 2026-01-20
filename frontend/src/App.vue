<script setup lang="ts">
import { ref, computed } from 'vue' 
import LibrarySidebar from './components/sidebar/LibrarySidebar.vue'
import PdfViewer from './components/pdf/PdfViewer.vue'
import AiPanel from './components/ai-panel/AiPanel.vue'
import ChatTab from './components/ai-panel/ChatTab.vue' 
import { useLibraryStore } from './stores/library'
import { useAiStore } from './stores/ai'

const libraryStore = useLibraryStore()
const aiStore = useAiStore()

// State for split view layout
// 'default': 50/50, 'max-top': AI Panel expands, 'max-bottom': Chat expands
const splitMode = ref<'default' | 'max-top' | 'max-bottom'>('default')

// Dynamic classes for panels based on mode
const topPanelClass = computed(() => {
  switch (splitMode.value) {
    case 'max-top': return 'flex-1 overflow-hidden'  // 占据剩余所有空间，并裁剪内部溢出
    case 'max-bottom': return 'h-14 flex-none overflow-hidden' // 固定高度，只显示头部
    default: return 'flex-1 overflow-hidden' // 50%
  }
})

const bottomPanelClass = computed(() => {
  switch (splitMode.value) {
    case 'max-top': return 'h-10 flex-none overflow-hidden' // Minimized header only
    case 'max-bottom': return 'flex-1 overflow-hidden' // ~80% heigth or higher
    default: return 'flex-1 overflow-hidden' // 50%
  }
})

// Toggle functions
const toggleTop = () => {
  splitMode.value = splitMode.value === 'max-top' ? 'default' : 'max-top'
}

const toggleBottom = () => {
  splitMode.value = splitMode.value === 'max-bottom' ? 'default' : 'max-bottom'
}

const resetSplit = () => {
  splitMode.value = 'default'
}
</script>

<template>
  <div class="flex h-screen w-screen bg-gray-50">
    <!-- Left Sidebar - Library -->
    <LibrarySidebar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex flex-1 overflow-hidden">
      <!-- PDF Viewer -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <PdfViewer />
      </div>

      <!-- Right Panel Container (Split View) -->
      <aside
        v-if="libraryStore.currentDocument"
        :class="[
          'flex flex-col border-l border-gray-200 bg-white transition-all duration-300 flex-shrink-0',
          aiStore.isPanelCollapsed ? 'w-0 opacity-0 overflow-hidden' : 'w-96'
        ]"
      >
        <!-- Top Half: AI Panel (Roadmap, Summary, Translation) -->
        <div 
          :class="['flex flex-col border-b border-gray-200 transition-all duration-300 ease-in-out', topPanelClass]"
        >
          <AiPanel />
        </div>
        <!--：
             1. z-50: 确保层级最高，不会被面板内容遮挡 
             2. group: 让鼠标靠近时能触发辅助线显示
        -->
        <!-- Splitter Controls (The Divider) -->
        <div class="h-0 relative z-50 flex items-center justify-center -my-3 group select-none">
             <!-- 悬停时显示的蓝色辅助线，帮助定位分隔处 -->
             <div class="absolute w-full h-6 bg-transparent flex items-center justify-center cursor-pointer pointer-events-none group-hover:pointer-events-auto">
               <div class="w-full h-0.5 bg-primary-200 opacity-0 group-hover:opacity-100 transition-opacity"></div>
             </div>

             <div class="bg-white border border-gray-200 rounded-full shadow-sm flex items-center gap-1 px-1 py-0.5 transform hover:scale-105 transition-transform cursor-pointer">
                <!-- Up Arrow (Maximize Top) -->
                <button 
                  @click="toggleTop" 
                  class="p-0.5 hover:bg-gray-100 rounded text-gray-500 hover:text-primary-600 transition-colors"
                  :class="{ 'text-primary-600 bg-primary-50': splitMode === 'max-top' }"
                  title="展开 AI 面板"
                >
                   <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
                </button>
                
                <!-- Reset (Center) -->
                <button 
                  v-if="splitMode !== 'default'"
                  @click="resetSplit"
                  class="p-0.5 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600 transition-colors"
                  title="恢复默认"
                >
                   <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 12h16" /></svg>
                </button>

                <!-- Down Arrow (Maximize Bottom) -->
                <button 
                   @click="toggleBottom"
                   class="p-0.5 hover:bg-gray-100 rounded text-gray-500 hover:text-primary-600 transition-colors"
                   :class="{ 'text-primary-600 bg-primary-50': splitMode === 'max-bottom' }"
                   title="展开聊天框"
                >
                   <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                </button>
             </div>
        </div>

        <!-- Bottom Half: Chat Box -->
        <div 
          :class="['flex flex-col overflow-hidden bg-gray-50 transition-all duration-300 ease-in-out relative z-10', bottomPanelClass]"
        >
          <!-- Chat Header -->
          <div 
            class="px-4 py-2 border-b border-gray-200 bg-white text-sm font-medium text-gray-700 shadow-sm z-10 flex-shrink-0 h-10 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            title="点击切换折叠状态"
            @click.self="splitMode === 'max-top' ? resetSplit() : (splitMode === 'default' ? toggleBottom() : null)"
          >
            <span>Chat & Ask</span>
            <button v-if="splitMode === 'max-top'" @click="resetSplit" class="text-xs text-primary-600 hover:underline font-normal">
               展开
             </button>
          </div>
          <ChatTab class="flex-1" />
        </div>
      </aside>
    </main>
  </div>
</template>
