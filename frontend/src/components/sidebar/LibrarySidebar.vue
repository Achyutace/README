<script setup lang="ts">
/*
----------------------------------------------------------------------
                            左侧边栏组件
----------------------------------------------------------------------
*/ 

// ------------------------- 导入依赖与 store -------------------------
// 从 Vue 导入响应式 API，以及需要的 store
import { ref, computed } from 'vue'
import { useLibraryStore } from '../../stores/library'
import { usePdfStore } from '../../stores/pdf'
import { useChatStore } from '../../stores/chat'
import { useRoadmapStore } from '../../stores/roadmap'
import { useAuthStore } from '../../stores/auth'
import { useRouter } from 'vue-router'

// ------------------------- 初始化 store 实例 -------------------------
// 组合式 store 实例用于访问应用级状态和方法
const libraryStore = useLibraryStore()
const pdfStore = usePdfStore()
const chatStore = useChatStore()
const roadmapStore = useRoadmapStore()
const authStore = useAuthStore()
const router = useRouter()

// 从库中获取所有唯一标签用于侧边栏展示
const uniqueTags = computed(() => libraryStore.allTags)

function handleLogout() {
  authStore.handleLogout()
}

// ------------------------- 初始化侧边栏折叠与交互状态 -------------------------
// 控制左侧边栏折叠 / 悬停状态，以及上传文件输入引用
const isCollapsed = ref(false) // 侧边栏是否折叠
const isHovering = ref(false) // 鼠标是否悬停在屏幕左边缘（显示折叠侧栏）
const fileInput = ref<HTMLInputElement | null>(null) // 文件输入引用

// 是否显示窄视图 (折叠且悬停时)
const showNarrowView = computed(() => isCollapsed.value && isHovering.value)
// 是否显示完整内容 (未折叠时)
const showFullContent = computed(() => !isCollapsed.value)

// ------------------------- 左侧边栏折叠控制 -------------------------
// 切换左侧边栏折叠状态
function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value // 状态取反
  // 展开时重置悬停状态
  if (!isCollapsed.value) isHovering.value = false
}

// 鼠标进入屏幕左边缘时显示侧边栏悬停状态
function handleEdgeMouseEnter() {
  // 如果侧边栏已折叠，则显示悬停状态
  if (isCollapsed.value) isHovering.value = true 
}

// 处理鼠标离开侧边栏悬停区域
function handleSidebarMouseLeave() {
  // 离开时取消悬停状态
  isHovering.value = false
}



// ------------------------- 文件上传流程 -------------------------
// 触发文件上传
function triggerFileUpload() {
  fileInput.value?.click()
}

// 处理文件上传，这是异步函数，接受一个事件参数
async function handleFileUpload(event: Event) {
  // 获取文件输入元素
  const target = event.target as HTMLInputElement

  // 获取上传的文件列表
  const files = target.files

  if (files && files.length > 0) {
    // 每次只处理一个文件的上传
    // TODO: 可以扩展为多文件上传
    const file = files[0]
    // 只处理 PDF 文件
    if (file && file.type === 'application/pdf') {
      try {
        chatStore.resetForNewDocument()
        roadmapStore.resetForNewDocument()

        // 添加文档到库中
        const doc = await libraryStore.addDocument(file)

        // 设置当前 PDF 文档
        pdfStore.setCurrentPdf(doc.url, doc.id) // 传递文档ID

        // 上传成功后自动收起左侧边栏
        isCollapsed.value = true



      } catch (error) {
        alert('上传失败，请确保后端服务已启动')
      }
    }
  }

  // 重置文件输入以允许上传同一文件
  target.value = ''
}

// ------------------------- 文档选择与删除 -------------------------
// 选择文档
async function selectDocument(id: string) {
  // 去库中查找对应文档
  const doc = libraryStore.documents.find((d: { id: string }) => d.id === id)
  // 如果找到则选择该文档
  if (doc) {
    chatStore.resetForNewDocument()
    roadmapStore.resetForNewDocument()
    await libraryStore.selectDocument(id) // 可能是异步，先拉取 blob
    pdfStore.setCurrentPdf(doc.url, doc.id) // 传递文档ID和最新的 url
    
    // 选择文献后自动收起左侧边栏
    isCollapsed.value = true
  }
}

// 删除文档（同时清理对应的高亮）
function removeDocument(id: string, event: Event) {
  event.stopPropagation() // 阻止事件冒泡，避免触发选择文档
  pdfStore.removeDocumentHighlights(id) // 删除文档时清理对应的高亮（见 pdf.ts）
  libraryStore.removeDocument(id) // 删除文档（见 library.ts）
}

// ------------------------- 组件脚本结束 -------------------------
// ---------------------------------------------------------------


// ------------------------- 组件模板开始 -------------------------
// （以下内容可以在 F12 开发者工具中查看）
</script>

<template>
  <div class="h-full flex-shrink-0 relative">
    <!-- 左边缘悬停检测区域 (折叠时显示) -->
    <div
      v-if="isCollapsed && !isHovering"
      class="h-full w-3 bg-transparent hover:bg-primary-500/20 transition-colors cursor-pointer"
      @mouseenter="handleEdgeMouseEnter"
    ></div>

    <!-- 侧边栏主体 -->
    <aside
      v-show="!isCollapsed || isHovering"
      @mouseleave="handleSidebarMouseLeave"
      :class="[
        'h-full bg-sidebar text-white flex flex-col transition-all duration-300',
        showNarrowView ? 'w-16' : 'w-60'
      ]"
    >
      <!-- Logo Area -->
      <div class="h-[42px] flex items-center justify-between px-4 pt-1">
        <h1 v-if="showFullContent" class="text-2xl font-extrabold tracking-tight text-primary-500 cursor-pointer" @click="router.push('/')">
          README
        </h1>
        <button
          @click="toggleSidebar"
          class="p-2 hover:bg-gray-700 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              :d="isCollapsed ? 'M13 5l7 7-7 7M5 5l7 7-7 7' : 'M11 19l-7-7 7-7M19 19l-7-7 7-7'"
            />
          </svg>
        </button>
      </div>

      <!-- Upload Button -->
      <div class="p-4">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf"
          class="hidden"
          @change="handleFileUpload"
        />
        <button
          @click="triggerFileUpload"
          class="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span v-if="showFullContent">上传 PDF</span>
        </button>
      </div>

      <!-- Document List -->
      <div class="flex-1 overflow-y-auto px-2 mt-2 space-y-4">
        
        <!-- 文献总库入口 -->
        <div>
          <div 
            v-if="showFullContent" 
            class="px-2 py-2 text-xs text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white flex items-center justify-between group"
            @click="router.push('/library')"
          >
            <span>文献库管理</span>
            <svg class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
          </div>
          <ul class="space-y-1">
            <li
              v-for="doc in libraryStore.documents"
              :key="doc.id"
              @click="selectDocument(doc.id)"
              :class="[
                'flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors group',
                libraryStore.currentDocumentId === doc.id
                  ? 'bg-primary-600/20 text-primary-400'
                  : 'hover:bg-gray-700/50 text-gray-300'
              ]"
            >
              <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span v-if="showFullContent" class="flex-1 truncate text-sm">
                {{ doc.name }}
              </span>
              <button
                v-if="showFullContent"
                @click="removeDocument(doc.id, $event)"
                class="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-600/20 rounded transition-all"
              >
                <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </li>
          </ul>
        </div>

        <!-- 标签分组入口 (由文献提取出的唯一标签) -->
        <div v-if="showFullContent && uniqueTags.length > 0">
           <div class="px-2 py-2 text-xs text-gray-400 uppercase tracking-wider">
            标签分组
          </div>
          <ul class="space-y-1 text-sm">
             <li
              v-for="tag in uniqueTags"
              :key="tag"
              @click="router.push(`/library?tag=${encodeURIComponent(tag)}`)"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-colors hover:bg-gray-700/50 text-gray-300"
            >
              <svg class="w-4 h-4 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path></svg>
              <span class="truncate">{{ tag }}</span>
            </li>
          </ul>
        </div>

        <!-- Empty State -->
        <div
          v-if="libraryStore.documents.length === 0 && showFullContent"
          class="text-center text-gray-500 py-8 px-4"
        >
          <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-sm">暂无文献</p>
          <p class="text-xs mt-1">点击上方按钮上传 PDF</p>
        </div>
      </div>

      <!-- User Info (Bottom) -->
      <div class="p-4 border-t border-gray-700">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-primary-600 rounded-full flex items-center justify-center">
            <span class="text-sm font-medium">{{ authStore.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</span>
          </div>
          <div v-if="showFullContent" class="flex-1 min-w-0">
            <p class="text-sm font-medium truncate">{{ authStore.user?.username || '用户' }}</p>
          </div>
          <button
            v-if="showFullContent"
            @click="handleLogout"
            class="p-1.5 hover:bg-gray-700 rounded-lg transition-colors flex-shrink-0"
            title="登出"
          >
            <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>


  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
