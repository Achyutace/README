<script setup lang="ts">
/*
----------------------------------------------------------------------
                            主应用组件
----------------------------------------------------------------------
*/ 

// ------------------------- 导入依赖与组件 -------------------------
// 从 Vue 导入响应式和生命周期 API
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
// 导入页面中使用到的子组件
import LibrarySidebar from './components/sidebar/LibrarySidebar.vue'
import PdfViewer from './components/pdf/PdfViewer.vue'
import PdfToolbar from './components/pdf/PdfToolbar.vue'
import NotesPanel from './components/notes/NotesPanel.vue'
import ChatTab from './components/chat-box/ChatTab.vue'
// 导入 Pinia store 的组合式使用函数（用于全局状态）
import { useLibraryStore } from './stores/library'
import { useAiStore } from './stores/ai'
import { usePdfStore } from './stores/pdf'
import { useThemeStore } from './stores/theme'
import { clip } from './utils/CommonFunction'

// ------------------------- 初始化 store 实例 -------------------------
// Store 本质上保存的是 应用状态 + 相关逻辑
// 通过组合式函数获取各个 store 的实例，供组件内部使用
const libraryStore = useLibraryStore()
const aiStore = useAiStore()
const pdfStore = usePdfStore()
const themeStore = useThemeStore()

// ------------------------- 初始化 Chat 和 Note 状态 -------------------------
// Chat 和 Note 是否可见
const notesVisible = ref(true)
const chatVisible = ref(true)

// Chat 和 Note 是否被折叠
const notesMinimized = ref(false)
const chatMinimized = ref(false)

// Sidebar 是否可见：至少有一个面板可见且不同时都最小化
const sidebarVisible = computed(() => {
  // 如果 Chat 或 Notes 其中一个可见，且不同时都最小化，则 Sidebar 可见
  const hasVisiblePanel = notesVisible.value || chatVisible.value
  const bothMinimized = notesVisible.value && notesMinimized.value 
    && chatVisible.value && chatMinimized.value
  return hasVisiblePanel && !bothMinimized
})

// Chat 占 Chat + Notes 的比例，默认 0.45
const splitRatio = ref(0.45) 

// 是否正在拖动分割条调整 Chat/Notes 高度
const isResizingSplit = ref(false) 

// 对整个 sidebar 的引用，类型可以是 HTML 元素或 null（初始值）
const sidebarRef = ref<HTMLElement | null>(null) 

// 对 Chat 面板的引用，不类型检查
const chatTabRef = ref<any>(null) 

// 对 Notes 面板的引用，不类型检查
const notesPanelRef = ref<any>(null) 

// 拖到底部或顶部时自动最小化的阈值（像素）
const SNAP_THRESHOLD = 60 

// ------------------------- 初始化右侧边栏 -------------------------
const sidebarWidth = ref(480) // 当前右侧边栏宽度（像素），默认 480px
const isResizingWidth = ref(false) // 是否正在拖动调整宽度
// 宽度上下限
const MIN_SIDEBAR_WIDTH = 380
const MAX_SIDEBAR_WIDTH = 650
// 分隔条比例上下限
const MIN_SPLIT_RATIO = 0.1
const MAX_SPLIT_RATIO = 0.9
// 默认分隔条位置（Chat 占比）
const DEFAULT_SPLIT_RATIO = 0.5

// ------------------------- Notes 和 Chat 切换 -------------------------
// 切换 Notes 面板可见性（工具栏按钮触发）
const toggleNotesVisibility = () => {
  notesVisible.value = !notesVisible.value // 对状态取反
}
// 切换 Chat 面板可见性（工具栏按钮触发）
const toggleChatVisibility = () => {
  chatVisible.value = !chatVisible.value // 对状态取反
}

// 切换 Notes 面板最小化/展开（面板头部点击触发）
const toggleNotesMinimize = () => {
  notesMinimized.value = !notesMinimized.value
  // 如果两个面板都最小化了，则自动隐藏它们并重置最小化状态
  if (notesMinimized.value && chatMinimized.value) {
    notesVisible.value = false
    chatVisible.value = false
    notesMinimized.value = false
    chatMinimized.value = false
  }
}
// 切换 Chat 面板最小化/展开（面板头部点击触发）
const toggleChatMinimize = () => {
  chatMinimized.value = !chatMinimized.value
  // 如果两个面板都最小化了，则自动隐藏它们并重置最小化状态
  if (notesMinimized.value && chatMinimized.value) {
    notesVisible.value = false
    chatVisible.value = false
    notesMinimized.value = false
    chatMinimized.value = false
  }
}

// 键盘快捷键处理：监听 Ctrl+Alt+/ 与 Ctrl+Alt+N
const handleKeyboard = (e: KeyboardEvent) => {
  // Ctrl+Alt+/ 切换 Chat 最小化
  if (e.ctrlKey && e.altKey && e.key === '/') {
    e.preventDefault() // 阻止浏览器默认行为
    toggleChatMinimize() // 切换 Chat 最小化状态
  }
  // Ctrl+Alt+N 切换 Notes 可见性
  if (e.ctrlKey && e.altKey && (e.key === 'n' || e.key === 'N')) {
    e.preventDefault() // 阻止浏览器默认行为
    toggleNotesMinimize() // 切换 Notes 最小化状态
  }
}

// ------------------------------- 侧边栏缩放 --------------------------------
// 开始调整宽度（点击分割条时触发）
const startWidthResize = (e: MouseEvent) => {
  if (!sidebarVisible.value) return // 不可见时不允许调整
  isResizingWidth.value = true // 正在调整宽度
  
  // 动态注册全局监听
  document.addEventListener('mousemove', handleWidthResize)
  document.addEventListener('mouseup', stopWidthResize)
  
  e.preventDefault() // 阻止浏览器默认行为，避免选中文本
}

// 处理宽度调整（鼠标移动时触发）
const handleWidthResize = (e: MouseEvent) => {
  if (!isResizingWidth.value) return // 如果不在调整状态，直接返回
  const newWidth = window.innerWidth - e.clientX // 计算新宽度
  // 限制宽度在最小值 and 最大值之间
  sidebarWidth.value = clip(newWidth, MIN_SIDEBAR_WIDTH, MAX_SIDEBAR_WIDTH)
}

// 停止宽度调整（鼠标抬起时触发）
const stopWidthResize = () => {
  isResizingWidth.value = false
  document.removeEventListener('mousemove', handleWidthResize)
  document.removeEventListener('mouseup', stopWidthResize)
}

// ------------------------- Chat 和 Notes 分割条调整 -------------------------
// 开始分割条调整（点击分割条时触发）
const startSplitResize = (e: MouseEvent) => {
  // 如果有一个不可见/最小化，则不允许调整
  if (!notesVisible.value || notesMinimized.value || 
    !chatVisible.value || chatMinimized.value) return
  isResizingSplit.value = true // 标记正在调整分割条
  
  // 动态注册全局监听
  document.addEventListener('mousemove', handleSplitResize)
  document.addEventListener('mouseup', stopSplitResize)
  
  e.preventDefault() // 阻止浏览器默认行为
}

// 处理分割条移动（鼠标移动时触发）
const handleSplitResize = (e: MouseEvent) => {
  // 如果不在调整状态或状态栏不存在，直接返回
  if (!isResizingSplit.value || !sidebarRef.value) return
  // 计算调整后位置
  const rect = sidebarRef.value.getBoundingClientRect() // 获取侧边栏尺寸
  const relativeY = e.clientY - rect.top // 鼠标到顶部距离
  const totalHeight = rect.height // 侧边栏总高度
  
  // 限制比例在 0.1 - 0.9 之间，避免过度收缩
  let newRatio = relativeY / totalHeight // 计算新比例
  newRatio = clip(newRatio, MIN_SPLIT_RATIO, MAX_SPLIT_RATIO) // 限制在范围内
  
  splitRatio.value = newRatio // 更新比例
}

// 停止分割条调整（鼠标抬起时触发）
const stopSplitResize = () => {
  // 如果不在调整状态或状态栏不存在，直接返回
  if (!isResizingSplit.value || !sidebarRef.value) return
  // 计算当前上/下面板高度
  const rect = sidebarRef.value.getBoundingClientRect() // 获取侧边栏尺寸
  const topHeight = rect.height * splitRatio.value // Notes 面板高度
  const bottomHeight = rect.height * (1 - splitRatio.value) // Chat 面板高度
  
  // 如果 Notes 或者 Chat 面板高度小于阈值，则自动最小化该面板
  // 如果侧边栏高度 > 600，则本条件不会触发，而是会被 0.1 - 0.9 限制覆盖
  if (topHeight < SNAP_THRESHOLD) {
    notesMinimized.value = true
    splitRatio.value = DEFAULT_SPLIT_RATIO
  } else if (bottomHeight < SNAP_THRESHOLD) {
    chatMinimized.value = true
    splitRatio.value = DEFAULT_SPLIT_RATIO
  }
  // 停止调整状态
  isResizingSplit.value = false
  
  // 移除全局监听
  document.removeEventListener('mousemove', handleSplitResize)
  document.removeEventListener('mouseup', stopSplitResize)
}

// ------------------------- 通过 Chat 和 Notes 状态计算样式 -------------------------
const topPanelStyle = computed(() => {
  // 如果不可见
  if (!notesVisible.value) return { display: 'none' }
  // 如果最小化，则固定高度为 36px
  if (notesMinimized.value) return { height: '36px', flexShrink: 0 }
  
  // 当 Notes 展开且 Chat 隐藏/最小化时，Notes 占据剩余空间
  if (!chatVisible.value || chatMinimized.value) {
    return { flex: '1 1 auto' }
  }
  
  // 两者都展开时，使用 splitRatio 计算高度
  return { height: `calc(${splitRatio.value * 100}% - 2px)`, flexShrink: 0 }
})

const bottomPanelStyle = computed(() => {
  // 如果不可见
  if (!chatVisible.value) return { display: 'none' }
  // 如果最小化，则固定高度为 36px
  if (chatMinimized.value) return { height: '36px', flexShrink: 0 }
  
  // 当 Chat 展开且 Notes 隐藏/最小化时，Chat 占据剩余空间
  if (!notesVisible.value || notesMinimized.value) {
    return { flex: '1 1 auto' }
  }
  
  // 两者都展开时，使用 splitRatio 计算高度
  return { height: `calc(${(1 - splitRatio.value) * 100}% - 2px)`, flexShrink: 0 }
})

// ------------------------- 在组件挂载/卸载时，注册/移除全局事件-------------------------
onMounted(() => {
  // 键盘按下 -> 处理快捷键（全局一直监听）
  document.addEventListener('keydown', handleKeyboard)
})

onBeforeUnmount(() => {
  // 移除键盘监听
  document.removeEventListener('keydown', handleKeyboard)

  // 防御性移除：防止组件卸载时仍处于拖拽状态
  document.removeEventListener('mousemove', handleWidthResize)
  document.removeEventListener('mousemove', handleSplitResize)
  
  document.removeEventListener('mouseup', stopWidthResize)
  document.removeEventListener('mouseup', stopSplitResize)
})


// ------------------------- 组件模板开始 -------------------------
</script>

<template>
  <div class="flex h-screen w-screen bg-gradient-to-br from-gray-50 to-gray-100/50 dark:from-[#1e1e1e] dark:to-[#252526] transition-colors duration-200">
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
              @toggle-theme="themeStore.toggleTheme"
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