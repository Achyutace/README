<script setup lang="ts">
import { ref, computed } from 'vue' 
import LibrarySidebar from './components/sidebar/LibrarySidebar.vue'
import PdfViewer from './components/pdf/PdfViewer.vue'
import PdfToolbar from './components/pdf/PdfToolbar.vue'
import AiPanel from './components/ai-panel/AiPanel.vue'
import ChatTab from './components/ai-panel/ChatTab.vue' 
import { useLibraryStore } from './stores/library'
import { useAiStore } from './stores/ai'
import { usePdfStore } from './stores/pdf'

const libraryStore = useLibraryStore()
const aiStore = useAiStore()
const pdfStore = usePdfStore()

// Panel minimize states
const topMinimized = ref(false)
const bottomMinimized = ref(false)

// Both minimized = sidebar collapses to thin bars
const bothMinimized = computed(() => topMinimized.value && bottomMinimized.value)

// Resizable sidebar width
const sidebarWidth = ref(384) // Default w-96 = 384px
const isResizingWidth = ref(false)
const MIN_WIDTH = 320
const MAX_WIDTH = 560
const MINIMIZED_WIDTH = 180 // Width when both panels are minimized (half of toolbar width ~360px)

const effectiveSidebarWidth = computed(() => {
  if (bothMinimized.value) return MINIMIZED_WIDTH
  return sidebarWidth.value
})

// Vertical split ratio (0 to 1, representing top panel percentage)
const splitRatio = ref(0.5)
const isResizingSplit = ref(false)
const sidebarRef = ref<HTMLElement | null>(null)

const SNAP_THRESHOLD = 60 // Distance from edge to trigger auto-minimize

// Toggle minimize for top panel
const toggleTopMinimize = () => {
  if (topMinimized.value) {
    // Expanding top panel
    topMinimized.value = false
    if (!bottomMinimized.value) {
      splitRatio.value = 0.5 // Reset to 50/50
    }
  } else {
    // Minimizing top panel
    topMinimized.value = true
  }
}

// Toggle minimize for bottom panel
const toggleBottomMinimize = () => {
  if (bottomMinimized.value) {
    // Expanding bottom panel
    bottomMinimized.value = false
    if (!topMinimized.value) {
      splitRatio.value = 0.5 // Reset to 50/50
    }
  } else {
    // Minimizing bottom panel
    bottomMinimized.value = true
  }
}

// Horizontal resize (sidebar width)
const startWidthResize = (e: MouseEvent) => {
  if (bothMinimized.value) return // Don't resize when both minimized
  isResizingWidth.value = true
  document.addEventListener('mousemove', handleWidthResize)
  document.addEventListener('mouseup', stopWidthResize)
  e.preventDefault()
}

const handleWidthResize = (e: MouseEvent) => {
  if (!isResizingWidth.value) return
  const windowWidth = window.innerWidth
  const newWidth = windowWidth - e.clientX
  sidebarWidth.value = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, newWidth))
}

const stopWidthResize = () => {
  isResizingWidth.value = false
  document.removeEventListener('mousemove', handleWidthResize)
  document.removeEventListener('mouseup', stopWidthResize)
}

// Vertical resize (split between panels)
const startSplitResize = (e: MouseEvent) => {
  if (topMinimized.value || bottomMinimized.value) return
  isResizingSplit.value = true
  document.addEventListener('mousemove', handleSplitResize)
  document.addEventListener('mouseup', stopSplitResize)
  e.preventDefault()
}

const handleSplitResize = (e: MouseEvent) => {
  if (!isResizingSplit.value || !sidebarRef.value) return
  
  const rect = sidebarRef.value.getBoundingClientRect()
  const relativeY = e.clientY - rect.top
  const totalHeight = rect.height
  
  // Calculate new ratio
  let newRatio = relativeY / totalHeight
  newRatio = Math.max(0.1, Math.min(0.9, newRatio))
  
  splitRatio.value = newRatio
}

const stopSplitResize = () => {
  if (!isResizingSplit.value || !sidebarRef.value) return
  
  const rect = sidebarRef.value.getBoundingClientRect()
  const topHeight = rect.height * splitRatio.value
  const bottomHeight = rect.height * (1 - splitRatio.value)
  
  // Auto-minimize if dragged to edge
  if (topHeight < SNAP_THRESHOLD) {
    topMinimized.value = true
    splitRatio.value = 0.5
  } else if (bottomHeight < SNAP_THRESHOLD) {
    bottomMinimized.value = true
    splitRatio.value = 0.5
  }
  
  isResizingSplit.value = false
  document.removeEventListener('mousemove', handleSplitResize)
  document.removeEventListener('mouseup', stopSplitResize)
}

// Computed styles for panels
const topPanelStyle = computed(() => {
  if (topMinimized.value) {
    return { height: '36px', flexGrow: 0, flexShrink: 0 }
  }
  if (bottomMinimized.value) {
    return { flexGrow: 1 }
  }
  return { height: `${splitRatio.value * 100}%`, flexGrow: 0, flexShrink: 0 }
})

const bottomPanelStyle = computed(() => {
  if (bottomMinimized.value) {
    return { height: '36px', flexGrow: 0, flexShrink: 0 }
  }
  if (topMinimized.value) {
    return { flexGrow: 1 }
  }
  return { flexGrow: 1 }
})
</script>

<template>
  <div class="flex h-screen w-screen bg-gray-50">
    <!-- Left Sidebar - Library -->
    <LibrarySidebar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- When both minimized: Top Row = Toolbar + Minimized Bars -->
      <template v-if="bothMinimized">
        <div class="flex items-stretch bg-white border-b border-gray-200 shadow-sm">
          <!-- PDF Toolbar -->
          <div class="flex-1">
            <PdfToolbar v-if="pdfStore.currentPdfUrl" />
            <div v-else class="h-[49px]"></div>
          </div>
          
          <!-- Right side minimized bars (horizontal layout) -->
          <div 
            v-if="libraryStore.currentDocument && !aiStore.isPanelCollapsed"
            class="flex border-l border-gray-200"
            :style="{ width: MINIMIZED_WIDTH + 'px' }"
          >
            <!-- Top panel minimized bar -->
            <div 
              class="flex-1 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors border-r border-gray-600"
              @click="toggleTopMinimize"
            >
              <!-- Triangle pointing up (minimized state) -->
              <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 14l5-5 5 5H7z"/>
              </svg>
              <span class="text-white text-xs font-medium truncate">AI</span>
            </div>
            <!-- Bottom panel minimized bar -->
            <div 
              class="flex-1 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors"
              @click="toggleBottomMinimize"
            >
              <!-- Triangle pointing up (minimized state) -->
              <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 14l5-5 5 5H7z"/>
              </svg>
              <span class="text-white text-xs font-medium truncate">Chat</span>
            </div>
          </div>
        </div>
        
        <!-- PDF Viewer fullscreen -->
        <div class="flex-1 overflow-hidden">
          <PdfViewer />
        </div>
      </template>

      <!-- Normal state: PDF area (with toolbar) on left, Right panels on right -->
      <template v-else>
        <div class="flex flex-1 overflow-hidden">
          <!-- Left: PDF Viewer with its toolbar -->
          <div class="flex-1 flex flex-col overflow-hidden">
            <div class="bg-white border-b border-gray-200 shadow-sm">
              <PdfToolbar v-if="pdfStore.currentPdfUrl" />
              <div v-else class="h-[49px]"></div>
            </div>
            <PdfViewer />
          </div>

          <!-- Right Panel Container (Split View) -->
        <aside
          v-if="libraryStore.currentDocument && !bothMinimized"
          ref="sidebarRef"
          class="flex flex-col border-l border-gray-200 bg-white flex-shrink-0 relative transition-all duration-200"
          :class="aiStore.isPanelCollapsed ? 'w-0 opacity-0 overflow-hidden' : ''"
          :style="!aiStore.isPanelCollapsed ? { width: effectiveSidebarWidth + 'px' } : {}"
        >
          <!-- Width Resize Handle -->
          <div
            v-if="!aiStore.isPanelCollapsed"
            class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-primary-400 transition-colors z-50"
            :class="{ 'bg-primary-500': isResizingWidth }"
            @mousedown="startWidthResize"
          >
            <div class="absolute left-0 top-0 bottom-0 w-3 -ml-1"></div>
          </div>

          <!-- Top Panel: AI Panel -->
          <div 
            class="flex flex-col border-b border-gray-200 overflow-hidden transition-all duration-200"
            :style="topPanelStyle"
          >
            <!-- Minimized Bar for Top Panel -->
            <div 
              v-if="topMinimized"
              class="h-9 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors"
              @click="toggleTopMinimize"
            >
              <!-- Triangle pointing up (minimized state) -->
              <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 14l5-5 5 5H7z"/>
              </svg>
              <span class="text-white text-xs font-medium truncate">AI 助手</span>
            </div>
            <!-- Full Panel Content -->
            <template v-else>
              <!-- Panel Header with Minimize Button -->
              <div class="flex items-center px-3 py-2 border-b border-gray-100 bg-white">
                <button
                  @click="toggleTopMinimize"
                  class="p-1 hover:bg-gray-100 rounded transition-colors mr-2"
                  title="最小化"
                >
                  <!-- Triangle pointing down (to collapse) -->
                  <svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M7 10l5 5 5-5H7z"/>
                  </svg>
                </button>
                <span class="text-sm font-medium text-gray-700">AI 助手</span>
              </div>
              <div class="flex-1 overflow-hidden">
                <AiPanel />
              </div>
            </template>
          </div>

          <!-- Draggable Divider (only show when neither panel is minimized) -->
          <div 
            v-if="!topMinimized && !bottomMinimized"
            class="h-1 bg-gray-200 hover:bg-primary-400 cursor-ns-resize transition-colors relative z-20 flex-shrink-0"
            :class="{ 'bg-primary-500': isResizingSplit }"
            @mousedown="startSplitResize"
          >
            <div class="absolute -top-1 -bottom-1 left-0 right-0"></div>
          </div>

          <!-- Bottom Panel: Chat Box -->
          <div 
            class="flex flex-col overflow-hidden bg-gray-50 transition-all duration-200"
            :style="bottomPanelStyle"
          >
            <!-- Minimized Bar for Bottom Panel -->
            <div 
              v-if="bottomMinimized"
              class="h-9 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors"
              @click="toggleBottomMinimize"
            >
              <!-- Triangle pointing up (minimized state) -->
              <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 14l5-5 5 5H7z"/>
              </svg>
              <span class="text-white text-xs font-medium truncate">Chat & Ask</span>
            </div>
            <!-- Full Panel Content -->
            <template v-else>
              <!-- Panel Header with Minimize Button -->
              <div class="flex items-center px-3 py-2 border-b border-gray-200 bg-white">
                <button
                  @click="toggleBottomMinimize"
                  class="p-1 hover:bg-gray-100 rounded transition-colors mr-2"
                  title="最小化"
                >
                  <!-- Triangle pointing down (expanded state) -->
                  <svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M7 10l5 5 5-5H7z"/>
                  </svg>
                </button>
                <span class="text-sm font-medium text-gray-700">Chat & Ask</span>
              </div>
              <ChatTab class="flex-1 overflow-hidden" />
            </template>
          </div>
        </aside>
        </div>
      </template>
    </main>
  </div>
</template>
