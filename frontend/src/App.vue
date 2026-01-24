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

// 三栏面板折叠状态
const notesCollapsed = ref(false)
const translationCollapsed = ref(true) // 翻译栏默认折叠
const chatCollapsed = ref(false)

// Resizable sidebar width
const sidebarWidth = ref(520)
const isResizingWidth = ref(false)
const MIN_SIDEBAR_WIDTH = 420
const MAX_SIDEBAR_WIDTH = 750

// 三栏高度比例
const splitRatio1 = ref(0.35) // notes占比
const splitRatio2 = ref(0.35) // chat占比
const isResizingSplit1 = ref(false)
const isResizingSplit2 = ref(false)
const sidebarRef = ref<HTMLElement | null>(null)
const chatTabRef = ref<any>(null)
const notesPanelRef = ref<any>(null)

const COLLAPSE_HEADER_HEIGHT = 32

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
  const dx = Math.abs(e.clientX - dragStartPos.value.x)
  const dy = Math.abs(e.clientY - dragStartPos.value.y)
  if (dx > 5 || dy > 5) {
    hasDragged.value = true
  }
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  themeButtonPos.value = {
    x: Math.max(0, Math.min(window.innerWidth - 44, newX)),
    y: Math.max(0, Math.min(window.innerHeight - 44, newY))
  }
}

const stopDragThemeButton = () => {
  isDraggingThemeButton.value = false
}

const handleThemeButtonClick = () => {
  if (!hasDragged.value) {
    themeStore.toggleTheme()
  }
}

// 切换面板折叠
const toggleNotes = () => { notesCollapsed.value = !notesCollapsed.value }
const toggleTranslation = () => { translationCollapsed.value = !translationCollapsed.value }
const toggleChat = () => { chatCollapsed.value = !chatCollapsed.value }

// Horizontal resize (sidebar width)
const startWidthResize = (e: MouseEvent) => {
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

// 第一条分隔条拖动（notes-translation之间）
const startSplit1Resize = (e: MouseEvent) => {
  isResizingSplit1.value = true
  document.addEventListener('mousemove', handleSplit1Resize)
  document.addEventListener('mouseup', stopSplit1Resize)
  e.preventDefault()
}

const handleSplit1Resize = (e: MouseEvent) => {
  if (!isResizingSplit1.value || !sidebarRef.value) return
  const rect = sidebarRef.value.getBoundingClientRect()
  const relativeY = e.clientY - rect.top
  const totalHeight = rect.height
  let newRatio = relativeY / totalHeight
  newRatio = Math.max(0.1, Math.min(0.6, newRatio))
  splitRatio1.value = newRatio
}

const stopSplit1Resize = () => {
  isResizingSplit1.value = false
  document.removeEventListener('mousemove', handleSplit1Resize)
  document.removeEventListener('mouseup', stopSplit1Resize)
}

// 第二条分隔条拖动（translation-chat之间）
const startSplit2Resize = (e: MouseEvent) => {
  isResizingSplit2.value = true
  document.addEventListener('mousemove', handleSplit2Resize)
  document.addEventListener('mouseup', stopSplit2Resize)
  e.preventDefault()
}

const handleSplit2Resize = (e: MouseEvent) => {
  if (!isResizingSplit2.value || !sidebarRef.value) return
  const rect = sidebarRef.value.getBoundingClientRect()
  const relativeY = e.clientY - rect.top
  const totalHeight = rect.height
  // 计算chat占比（从底部算起）
  let chatRatio = (totalHeight - relativeY) / totalHeight
  chatRatio = Math.max(0.1, Math.min(0.6, chatRatio))
  splitRatio2.value = chatRatio
}

const stopSplit2Resize = () => {
  isResizingSplit2.value = false
  document.removeEventListener('mousemove', handleSplit2Resize)
  document.removeEventListener('mouseup', stopSplit2Resize)
}

// 翻译面板是否隐藏（暂时隐藏用于测试UI）
const translationHidden = ref(true)

// 计算各面板高度样式
const notesPanelStyle = computed(() => {
  if (notesCollapsed.value) return { height: COLLAPSE_HEADER_HEIGHT + 'px', flexShrink: 0 }

  // 如果翻译面板隐藏，notes和chat平分空间（减去折叠的header高度）
  if (translationHidden.value) {
    if (chatCollapsed.value) {
      // chat折叠时，notes占满剩余空间
      return { height: `calc(100% - ${COLLAPSE_HEADER_HEIGHT}px)`, flexShrink: 0 }
    }
    // 两面板都展开，按比例分配
    const totalRatio = splitRatio1.value + splitRatio2.value
    const notesRatio = splitRatio1.value / totalRatio
    return { height: `${notesRatio * 100}%`, flexShrink: 0 }
  }

  return { height: `${splitRatio1.value * 100}%`, flexShrink: 0 }
})

const translationPanelStyle = computed(() => {
  if (translationCollapsed.value) return { height: COLLAPSE_HEADER_HEIGHT + 'px', flexShrink: 0 }
  const translationRatio = 1 - splitRatio1.value - splitRatio2.value
  return { height: `${Math.max(0.1, translationRatio) * 100}%`, flexShrink: 0 }
})

const chatPanelStyle = computed(() => {
  if (chatCollapsed.value) return { height: COLLAPSE_HEADER_HEIGHT + 'px', flexShrink: 0 }

  // 如果翻译面板隐藏，notes和chat平分空间
  if (translationHidden.value) {
    if (notesCollapsed.value) {
      // notes折叠时，chat占满剩余空间
      return { height: `calc(100% - ${COLLAPSE_HEADER_HEIGHT}px)`, flexShrink: 0 }
    }
    // 两面板都展开，按比例分配
    const totalRatio = splitRatio1.value + splitRatio2.value
    const chatRatio = splitRatio2.value / totalRatio
    return { height: `${chatRatio * 100}%`, flexShrink: 0 }
  }

  return { height: `${splitRatio2.value * 100}%`, flexShrink: 0 }
})

onMounted(() => {
  document.addEventListener('mousemove', onDragThemeButton)
  document.addEventListener('mouseup', stopDragThemeButton)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDragThemeButton)
  document.removeEventListener('mouseup', stopDragThemeButton)
})
</script>

<template>
  <div class="flex h-screen w-screen bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-[#111827] dark:to-[#0b1220] transition-colors duration-200">
    <!-- Theme Toggle Button -->
    <button
      @click="handleThemeButtonClick"
      @mousedown="startDragThemeButton"
      class="fixed z-[9999] p-2.5 rounded-lg bg-white/90 dark:bg-[#2d2d30] hover:bg-gray-100 dark:hover:bg-[#3e3e42] border border-gray-200/60 dark:border-gray-700/60 shadow-lg transition-colors duration-200 cursor-move select-none"
      :style="{ left: themeButtonPos.x + 'px', top: themeButtonPos.y + 'px' }"
      title="切换主题 (可拖动)"
    >
      <svg v-if="themeStore.isDarkMode" class="w-5 h-5 text-yellow-500 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
      <svg v-else class="w-5 h-5 text-gray-700 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    </button>
    
    <!-- Left Sidebar - Library -->
    <LibrarySidebar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- Top Row: Toolbar -->
      <div class="flex items-stretch bg-white/95 dark:bg-sidebar backdrop-blur-sm border-b border-gray-200/60 dark:border-[#121726]/70 shadow-sm">
        <div class="flex-1">
          <PdfToolbar
            v-if="pdfStore.currentPdfUrl"
            :notes-minimized="notesCollapsed"
            :chat-minimized="chatCollapsed"
            @toggle-notes="toggleNotes"
            @toggle-chat="toggleChat"
          />
          <div v-else class="h-[49px]"></div>
        </div>
      </div>

      <!-- Content Row: PDF Viewer + Right Panels -->
      <div class="flex flex-1 overflow-hidden">
        <!-- PDF Viewer -->
        <div class="flex-1 overflow-hidden">
          <PdfViewer />
        </div>

        <!-- Right Panel Container - 三栏布局 -->
        <aside
          v-if="libraryStore.currentDocument"
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

          <!-- Panel 1: 笔记 -->
          <div
            class="flex flex-col border-b border-gray-200 dark:border-[#121726]/70 overflow-hidden transition-all duration-200"
            :style="notesPanelStyle"
          >
            <div class="flex items-center justify-between px-3 py-1.5 border-b border-gray-100 dark:border-[#121726]/70 bg-white dark:bg-sidebar cursor-pointer select-none"
                 @click="toggleNotes">
              <div class="flex items-center gap-2">
                <svg class="w-3 h-3 text-gray-400 transition-transform" :class="{ '-rotate-90': notesCollapsed }" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 10l5 5 5-5H7z"/>
                </svg>
                <span class="text-xs font-medium text-gray-600 dark:text-gray-300">笔记</span>
              </div>
              <button
                v-if="!notesCollapsed"
                @click.stop="notesPanelRef?.addCard()"
                class="p-1 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded transition-colors"
                title="添加卡片"
              >
                <svg class="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
            <div v-if="!notesCollapsed" class="flex-1 overflow-hidden">
              <NotesPanel ref="notesPanelRef" />
            </div>
          </div>

          <!-- Divider 1: notes-translation (暂时隐藏) -->
          <div
            v-if="!translationHidden && !notesCollapsed && !translationCollapsed"
            class="h-1 bg-gray-200 dark:bg-[#2f3750] hover:bg-primary-400 dark:hover:bg-primary-500 cursor-ns-resize transition-colors relative z-20 flex-shrink-0"
            :class="{ 'bg-primary-500': isResizingSplit1 }"
            @mousedown="startSplit1Resize"
          >
            <div class="absolute -top-2 -bottom-2 left-0 right-0"></div>
          </div>

          <!-- Divider: notes-chat (翻译面板隐藏时显示) -->
          <div
            v-if="translationHidden && !notesCollapsed && !chatCollapsed"
            class="h-1 bg-gray-300 dark:bg-[#2f3750] hover:bg-primary-400 dark:hover:bg-primary-500 cursor-ns-resize transition-colors relative z-20 flex-shrink-0"
            :class="{ 'bg-primary-500': isResizingSplit1 }"
            @mousedown="startSplit1Resize"
          >
            <div class="absolute -top-2 -bottom-2 left-0 right-0"></div>
          </div>

          <!-- Panel 2: 翻译 (暂时隐藏) -->
          <div
            v-if="!translationHidden"
            class="flex flex-col border-b border-gray-200 dark:border-[#121726]/70 overflow-hidden transition-all duration-200"
            :style="translationPanelStyle"
          >
            <div class="flex items-center justify-between px-3 py-1.5 border-b border-gray-100 dark:border-[#121726]/70 bg-white dark:bg-sidebar cursor-pointer select-none"
                 @click="toggleTranslation">
              <div class="flex items-center gap-2">
                <svg class="w-3 h-3 text-gray-400 transition-transform" :class="{ '-rotate-90': translationCollapsed }" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 10l5 5 5-5H7z"/>
                </svg>
                <span class="text-xs font-medium text-gray-600 dark:text-gray-300">翻译</span>
                <span v-if="pdfStore.sidebarDockedPanels.length > 0" class="text-[10px] text-gray-400 dark:text-gray-500">
                  ({{ pdfStore.sidebarDockedPanels.length }})
                </span>
              </div>
            </div>
            <div v-if="!translationCollapsed" class="flex-1 overflow-y-auto bg-gray-50/50 dark:bg-[#1a1a1a]">
              <!-- 已停靠的翻译面板列表 -->
              <div v-if="pdfStore.sidebarDockedPanels.length > 0" class="divide-y divide-gray-100 dark:divide-[#2a2a2a]">
                <div 
                  v-for="(panelId, idx) in pdfStore.sidebarDockedPanels" 
                  :key="panelId"
                  class="group"
                >
                  <div 
                    v-for="panel in pdfStore.translationPanels.filter(p => p.id === panelId)"
                    :key="panel.id"
                    class="p-4 hover:bg-white/50 dark:hover:bg-[#222] transition-colors"
                  >
                    <!-- 卡片头部 -->
                    <div class="flex items-center justify-between mb-3">
                      <div class="flex items-center gap-2">
                        <span class="w-5 h-5 flex items-center justify-center rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-[10px] font-medium">
                          {{ idx + 1 }}
                        </span>
                        <span class="text-[11px] text-gray-500 dark:text-gray-400 font-medium">段落翻译</span>
                      </div>
                      <button
                        @click="pdfStore.closeTranslationPanelById(panel.id)"
                        class="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 dark:hover:bg-[#3e3e42] rounded transition-all"
                        title="移除"
                      >
                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <!-- 翻译内容 -->
                    <div v-if="panel.isLoading" class="flex items-center gap-2 py-3 text-gray-400 dark:text-gray-500">
                      <div class="w-4 h-4 border-2 border-gray-300 dark:border-gray-600 border-t-blue-500 dark:border-t-blue-400 rounded-full animate-spin"></div>
                      <span class="text-xs">翻译中...</span>
                    </div>
                    <div 
                      v-else 
                      class="text-[13px] text-gray-700 dark:text-gray-300 leading-[1.7] tracking-wide"
                      style="text-align: justify; word-break: break-word;"
                    >
                      {{ panel.translation || '暂无翻译' }}
                    </div>
                  </div>
                </div>
              </div>
              <!-- 空状态 -->
              <div v-else class="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500 p-4">
                <svg class="w-8 h-8 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                </svg>
                <p class="text-xs text-center">拖动翻译面板到右侧停靠</p>
              </div>
            </div>
          </div>

          <!-- Divider 2: translation-chat (暂时隐藏) -->
          <div
            v-if="!translationHidden && !translationCollapsed && !chatCollapsed"
            class="h-1 bg-gray-200 dark:bg-[#2f3750] hover:bg-primary-400 dark:hover:bg-primary-500 cursor-ns-resize transition-colors relative z-20 flex-shrink-0"
            :class="{ 'bg-primary-500': isResizingSplit2 }"
            @mousedown="startSplit2Resize"
          >
            <div class="absolute -top-2 -bottom-2 left-0 right-0"></div>
          </div>

          <!-- Panel 3: Chat -->
          <div 
            class="flex flex-col overflow-hidden bg-gray-50 dark:bg-sidebar transition-all duration-200"
            :style="chatPanelStyle"
          >
            <div class="flex items-center justify-between px-3 py-1.5 border-b border-gray-100 dark:border-[#121726]/70 bg-white dark:bg-sidebar cursor-pointer select-none"
                 @click="toggleChat">
              <div class="flex items-center gap-2">
                <svg class="w-3 h-3 text-gray-400 transition-transform" :class="{ '-rotate-90': chatCollapsed }" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 10l5 5 5-5H7z"/>
                </svg>
                <span class="text-xs font-medium text-gray-600 dark:text-gray-300">Chat</span>
              </div>
              <button
                v-if="!chatCollapsed"
                class="p-1 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded transition-colors"
                title="聊天记录"
                @click.stop="chatTabRef?.toggleHistoryPanel()"
              >
                <svg class="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </div>
            <ChatTab v-if="!chatCollapsed" ref="chatTabRef" class="flex-1 overflow-hidden" />
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>