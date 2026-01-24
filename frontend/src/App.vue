<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import LibrarySidebar from './components/sidebar/LibrarySidebar.vue'
import PdfViewer from './components/pdf/PdfViewer.vue'
import PdfToolbar from './components/pdf/PdfToolbar.vue'
import NotesPanel from './components/notes/NotesPanel.vue'
import ChatTab from './components/chat-box/ChatTab.vue'
import { useLibraryStore } from './stores/library'
import { useAiStore } from './stores/ai'
import { usePdfStore } from './stores/pdf'
import { useThemeStore } from './stores/theme'

const libraryStore = useLibraryStore()
const aiStore = useAiStore()
const pdfStore = usePdfStore()
const themeStore = useThemeStore()

// --- Panel States ---
// Visible: Controlled by Toolbar buttons (Show/Hide)
const notesVisible = ref(true)
const chatVisible = ref(true)

// Minimized: Controlled by Panel Header buttons (Expand/Collapse)
const notesMinimized = ref(false)
const chatMinimized = ref(false)

// Sidebar is visible if at least one panel is visible and not both minimized
const sidebarVisible = computed(() => {
  const hasVisiblePanel = notesVisible.value || chatVisible.value
  const bothMinimized = notesVisible.value && notesMinimized.value && chatVisible.value && chatMinimized.value
  return hasVisiblePanel && !bothMinimized
})

// Resizable sidebar width
const sidebarWidth = ref(480) // Default w-96 = 384px
const isResizingWidth = ref(false)
const MIN_SIDEBAR_WIDTH = 380
const MAX_SIDEBAR_WIDTH = 650

// Vertical split ratio (0 to 1, representing top panel percentage)
const splitRatio = ref(0.45)
const isResizingSplit = ref(false)
const sidebarRef = ref<HTMLElement | null>(null)
const chatTabRef = ref<any>(null)
const notesPanelRef = ref<any>(null)

const SNAP_THRESHOLD = 60 // Distance from edge to trigger auto-minimize

// Theme toggle button drag state
const themeButtonPos = ref({ x: window.innerWidth - 60, y: 16 })
const isDraggingThemeButton = ref(false)
const hasDragged = ref(false)
const dragOffset = ref({ x: 0, y: 0 })
const dragStartPos = ref({ x: 0, y: 0 })

const startDragThemeButton = (e: MouseEvent) => {
  isDraggingThemeButton.value = true
  hasDragged.value = false
  dragStartPos.value = { x: e.clientX, y: e.clientY }
  dragOffset.value = {
    x: e.clientX - themeButtonPos.value.x,
    y: e.clientY - themeButtonPos.value.y
  }
  e.preventDefault()
}

const onDragThemeButton = (e: MouseEvent) => {
  if (!isDraggingThemeButton.value) return

  // Check if actually dragged (moved more than 5px)
  const dx = Math.abs(e.clientX - dragStartPos.value.x)
  const dy = Math.abs(e.clientY - dragStartPos.value.y)
  if (dx > 5 || dy > 5) {
    hasDragged.value = true
  }

  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  // Keep button within viewport bounds
  themeButtonPos.value = {
    x: Math.max(0, Math.min(window.innerWidth - 44, newX)),
    y: Math.max(0, Math.min(window.innerHeight - 44, newY))
  }
}

const stopDragThemeButton = () => {
  isDraggingThemeButton.value = false
}

const handleThemeButtonClick = () => {
  // Only toggle theme if not dragged
  if (!hasDragged.value) {
    themeStore.toggleTheme()
  }
}

// --- Toggles ---

// Toggle Visibility (Hide/Show)
const toggleNotesVisibility = () => {
  notesVisible.value = !notesVisible.value
}
const toggleChatVisibility = () => {
  chatVisible.value = !chatVisible.value
}

// Toggle Minimize (Collapse/Expand)
const toggleNotesMinimize = () => {
  notesMinimized.value = !notesMinimized.value
  // 如果两个都最小化了，自动隐藏它们
  if (notesMinimized.value && chatMinimized.value) {
    notesVisible.value = false
    chatVisible.value = false
    notesMinimized.value = false
    chatMinimized.value = false
  }
}
const toggleChatMinimize = () => {
  chatMinimized.value = !chatMinimized.value
  // 如果两个都最小化了，自动隐藏它们
  if (notesMinimized.value && chatMinimized.value) {
    notesVisible.value = false
    chatVisible.value = false
    notesMinimized.value = false
    chatMinimized.value = false
  }
}

// Keyboard shortcuts handler
const handleKeyboard = (e: KeyboardEvent) => {
  // Ctrl+Alt+/ toggle Chat Minimize (Keep existing shortcut behavior)
  if (e.ctrlKey && e.altKey && e.key === '/') {
    e.preventDefault()
    toggleChatMinimize()
  }
  // Ctrl+Alt+N toggle Notes Visibility (Hide/Show)
  if (e.ctrlKey && e.altKey && (e.key === 'n' || e.key === 'N')) {
    e.preventDefault()
    toggleNotesVisibility()
  }
}

onMounted(() => {
  document.addEventListener('mousemove', onDragThemeButton)
  document.addEventListener('mouseup', stopDragThemeButton)
  document.addEventListener('keydown', handleKeyboard)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDragThemeButton)
  document.removeEventListener('mouseup', stopDragThemeButton)
  document.removeEventListener('keydown', handleKeyboard)
})

// Horizontal resize (sidebar width)
const startWidthResize = (e: MouseEvent) => {
  if (!sidebarVisible.value) return // Don't resize when hidden
  isResizingWidth.value = true
  document.addEventListener('mousemove', handleWidthResize)
  document.addEventListener('mouseup', stopWidthResize)
  e.preventDefault()
}

const handleWidthResize = (e: MouseEvent) => {
  if (!isResizingWidth.value) return
  const windowWidth = window.innerWidth
  const newWidth = windowWidth - e.clientX
  sidebarWidth.value = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, newWidth))
}

const stopWidthResize = () => {
  isResizingWidth.value = false
  document.removeEventListener('mousemove', handleWidthResize)
  document.removeEventListener('mouseup', stopWidthResize)
}

// Vertical resize (split between panels)
const startSplitResize = (e: MouseEvent) => {
  // Only allow resize if both are visible and NOT minimized
  if (!notesVisible.value || notesMinimized.value || !chatVisible.value || chatMinimized.value) return
  
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
    notesMinimized.value = true
    splitRatio.value = 0.5
  } else if (bottomHeight < SNAP_THRESHOLD) {
    chatMinimized.value = true
    splitRatio.value = 0.5
  }
  
  isResizingSplit.value = false
  document.removeEventListener('mousemove', handleSplitResize)
  document.removeEventListener('mouseup', stopSplitResize)
}

// Computed styles for panels
const topPanelStyle = computed(() => {
  if (!notesVisible.value) return { display: 'none' }
  if (notesMinimized.value) return { height: '36px', flexShrink: 0 }
  
  // If Notes is expanded...
  // And Chat is hidden OR minimized -> Notes takes full remaining space
  if (!chatVisible.value || chatMinimized.value) {
    return { flex: '1 1 auto' }
  }
  
  // Both expanded -> Use split ratio
  return { height: `calc(${splitRatio.value * 100}% - 2px)`, flexShrink: 0 }
})

const bottomPanelStyle = computed(() => {
  if (!chatVisible.value) return { display: 'none' }
  if (chatMinimized.value) return { height: '36px', flexShrink: 0 }
  
  // If Chat is expanded...
  // And Notes is hidden OR minimized -> Chat takes full remaining space
  if (!notesVisible.value || notesMinimized.value) {
    return { flex: '1 1 auto' }
  }
  
  // Both expanded -> Use split ratio
  return { height: `calc(${(1 - splitRatio.value) * 100}% - 2px)`, flexShrink: 0 }
})
</script>

<template>
  <div class="flex h-screen w-screen bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-[#1e1e1e] dark:to-[#252526] transition-colors duration-200">
    <!-- Theme Toggle Button - Draggable, top layer -->
    <button
      @click="handleThemeButtonClick"
      @mousedown="startDragThemeButton"
      class="fixed z-[9999] p-2.5 rounded-lg bg-white/90 dark:bg-[#2d2d30] hover:bg-gray-100 dark:hover:bg-[#3e3e42] border border-gray-200/60 dark:border-gray-700/60 shadow-lg transition-colors duration-200 cursor-move select-none"
      :style="{ left: themeButtonPos.x + 'px', top: themeButtonPos.y + 'px' }"
      title="切换主题 (可拖动)"
    >
      <!-- Sun icon (show in dark mode) -->
      <svg v-if="themeStore.isDarkMode" class="w-5 h-5 text-yellow-500 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
      <!-- Moon icon (show in light mode) -->
      <svg v-else class="w-5 h-5 text-gray-700 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    </button>
    
    <!-- Left Sidebar - Library -->
    <LibrarySidebar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- Content Row: PDF Viewer + Right Panels -->
      <div class="flex flex-1 overflow-hidden">
        <!-- PDF Viewer - always present, never destroyed -->
        <div class="flex-1 overflow-hidden flex flex-col">
          <!-- PDF Toolbar - Only above PDF viewer -->
          <div class="bg-white/95 dark:bg-[#252526] backdrop-blur-sm border-b border-gray-200/60 dark:border-gray-800/60 shadow-sm">
            <PdfToolbar
              v-if="pdfStore.currentPdfUrl"
              :notes-visible="notesVisible"
              :chat-visible="chatVisible"
              @toggle-notes-visibility="toggleNotesVisibility"
              @toggle-chat-visibility="toggleChatVisibility"
            />
            <div v-else class="h-[49px]"></div>
          </div>
          <!-- PDF Viewer Content -->
        <div class="flex-1 overflow-hidden">
          <PdfViewer />
        </div>
        </div>

        <!-- Right Panel Container (Split View) - hidden when both panels are hidden -->
        <aside
          v-if="libraryStore.currentDocument"
          v-show="sidebarVisible"
          ref="sidebarRef"
          class="flex flex-col border-l border-gray-200/60 dark:border-gray-800/60 bg-white/95 dark:bg-[#1e1e1e] backdrop-blur-sm flex-shrink-0 relative transition-all duration-200 shadow-xl"
          :class="aiStore.isPanelHidden ? 'w-0 opacity-0 overflow-hidden' : ''"
          :style="!aiStore.isPanelHidden ? { width: sidebarWidth + 'px' } : {}"
        >
          <!-- Width Resize Handle -->
          <div
            v-if="!aiStore.isPanelHidden"
            class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-gray-400 dark:hover:bg-gray-600 transition-colors z-50"
            :class="{ 'bg-primary-500': isResizingWidth }"
            @mousedown="startWidthResize"
          >
            <div class="absolute left-0 top-0 bottom-0 w-3 -ml-1"></div>
          </div>

          <!-- Top Panel: AI Panel (Notes) -->
          <div
            v-if="notesVisible"
            class="flex flex-col border-b border-gray-200 dark:border-gray-800 overflow-hidden transition-all duration-200"
            :style="topPanelStyle"
          >
            <!-- Minimized Bar for Top Panel -->
            <div 
              v-if="notesMinimized"
              class="h-9 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors"
              @click="toggleNotesMinimize"
            >
               <!-- Down Triangle (Expand) -->
               <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 10l5 5 5-5H7z"/>
                </svg>
              <span class="text-white text-xs font-medium truncate">Note</span>
            </div>

            <template v-else>
            <!-- Panel Header with Minimize Button -->
            <div 
              class="h-9 flex items-center justify-between px-3 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-[#252526] cursor-pointer hover:bg-gray-50 dark:hover:bg-[#2d2d30] transition-colors"
              @click="toggleNotesMinimize"
            >
              <div class="flex items-center">
                <div class="mr-2 flex items-center text-gray-500 dark:text-gray-400">
                  <!-- Up Triangle (Collapse) -->
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M7 14l5-5 5 5H7z"/>
                  </svg>
                </div>
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Note</span>
              </div>
              <!-- Add Card Button -->
              <button
                @click.stop="notesPanelRef?.addCard()"
                class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="添加卡片"
              >
                <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
            <div class="flex-1 overflow-hidden">
              <NotesPanel ref="notesPanelRef" />
            </div>
            </template>
          </div>

          <!-- Spacer if both are minimized (to push chat to bottom) -->
          <div v-if="notesVisible && notesMinimized && chatVisible && chatMinimized" class="flex-1 bg-gray-50 dark:bg-[#1e1e1e]"></div>

          <!-- Draggable Divider (only show when both panels are visible and expanded) -->
          <div
            v-if="notesVisible && !notesMinimized && chatVisible && !chatMinimized"
            class="h-1 bg-gray-300 dark:bg-gray-700 hover:bg-primary-400 dark:hover:bg-primary-500 cursor-ns-resize transition-colors relative z-20 flex-shrink-0"
            :class="{ 'bg-primary-500 dark:bg-primary-400': isResizingSplit }"
            @mousedown="startSplitResize"
          >
            <!-- 扩展点击区域 -->
            <div class="absolute -top-2 -bottom-2 left-0 right-0"></div>
          </div>

          <!-- Bottom Panel: Chat Box -->
          <div
            v-if="chatVisible"
            class="flex flex-col overflow-hidden bg-gray-50 dark:bg-[#1e1e1e] transition-all duration-200"
            :style="bottomPanelStyle"
          >
            <!-- Minimized Bar for Bottom Panel -->
          <div
              v-if="chatMinimized"
              class="h-9 bg-gray-700 flex items-center px-3 cursor-pointer hover:bg-gray-600 transition-colors"
              @click="toggleChatMinimize"
            >
              <!-- Triangle pointing up (Expand) -->
              <svg class="w-4 h-4 text-white mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 14l5-5 5 5H7z"/>
                </svg>
              <span class="text-white text-xs font-medium truncate">Chat</span>
            </div>
            <!-- Full Panel Content -->
            <template v-else>
              <!-- Panel Header with Minimize Button and History -->
              <div 
                class="h-9 flex items-center justify-between px-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#252526] cursor-pointer hover:bg-gray-50 dark:hover:bg-[#2d2d30] transition-colors"
                @click="toggleChatMinimize"
              >
                <div class="flex items-center">
                  <div class="mr-2 flex items-center text-gray-500">
                    <!-- Triangle pointing down (Collapse) -->
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M7 10l5 5 5-5H7z"/>
                        </svg>
                  </div>
                  <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Chat</span>
          </div>

                <!-- Right Actions -->
                <div class="flex items-center gap-1">
                  <!-- New Chat Button -->
                  <button
                    class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-colors"
                    title="新对话"
                    @click.stop="chatTabRef?.createNewChat()"
                  >
                    <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                  </button>

                  <!-- History Button (Clock Icon) - Always visible -->
              <button
                    class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-colors"
                title="聊天记录"
                @click.stop="chatTabRef?.toggleHistoryPanel()"
              >
                    <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </div>
              </div>
              <ChatTab ref="chatTabRef" class="flex-1 overflow-hidden" />
            </template>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>