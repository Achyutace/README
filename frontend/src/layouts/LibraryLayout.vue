<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useLibraryStore } from '../stores/library'
import { useThemeStore } from '../stores/theme'
import { formatDate } from '../utils/date'
import type { PdfDocument } from '../types'

// ------------------------- Stores & Router -------------------------
const libraryStore = useLibraryStore()
const themeStore = useThemeStore()
const router = useRouter()
const route = useRoute()

// ------------------------- State -------------------------
const expandedPaperIds = ref<Set<string>>(new Set())
const loadingNotes = ref<Record<string, boolean>>({})
const newTagInputs = ref<Record<string, string>>({})
const searchQuery = ref('')
const isImporting = ref(false)
const isExporting = ref(false)

// ------------------------- Computed -------------------------
// 从路由或本地状态确定选中的标签 (文件夹)
const selectedFolder = computed(() => (route.query.tag as string) || 'all')

// 使用 Store 中统一计算的所有唯一标签用于左侧边栏
const folders = computed(() => libraryStore.allTags)

// 根据搜索和标签过滤文档
const filteredDocuments = computed(() => {
  return libraryStore.documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchesTag = selectedFolder.value === 'all' || (doc.tags && doc.tags.includes(selectedFolder.value))
    return matchesSearch && matchesTag
  })
})

// ------------------------- Actions -------------------------
const toggleExpand = async (pdfId: string) => {
  if (expandedPaperIds.value.has(pdfId)) {
    expandedPaperIds.value.delete(pdfId)
  } else {
    expandedPaperIds.value.add(pdfId)
    // 触发懒加载笔记
    if (!libraryStore.notesCache[pdfId]) {
      loadingNotes.value[pdfId] = true
      await libraryStore.getDocumentNotes(pdfId)
      loadingNotes.value[pdfId] = false
    }
  }
}

const selectFolder = (folder: string) => {
  if (folder === 'all') {
    router.push('/library')
  } else {
    router.push({ path: '/library', query: { tag: folder } })
  }
}

const openPaper = async (pdfId: string) => {
  // 切换文档并跳转回主页
  await libraryStore.selectDocument(pdfId)
  router.push('/')
}

const handleAddTag = async (pdfId: string, tagOverride?: string) => {
  const tag = (tagOverride || newTagInputs.value[pdfId] || '').trim()
  if (tag) {
    const success = await libraryStore.addTagToDocument(pdfId, tag)
    if (success) {
      newTagInputs.value[pdfId] = ''
    }
  }
}

const getSuggestedTags = (doc: PdfDocument) => {
  const query = (newTagInputs.value[doc.id] || '').toLowerCase()
  return folders.value.filter(tag => 
    !(doc.tags && doc.tags.includes(tag)) && 
    tag.toLowerCase().includes(query)
  )
}

const handleRemoveTag = async (pdfId: string, tag: string) => {
  await libraryStore.removeTagFromDocument(pdfId, tag)
}



const handleZoteroImport = () => {
  isImporting.value = true
  setTimeout(() => {
    alert('正在检测本地 Zotero 数据库... (功能目前为 UI 预览)')
    isImporting.value = false
  }, 1000)
}

const handleExportAll = () => {
  isExporting.value = true
  setTimeout(() => {
    alert('正在导出全部文献与笔记... (功能目前为 UI 预览)')
    isExporting.value = false
  }, 1000)
}

onMounted(() => {
  // 确保数据已同步
  libraryStore.fetchDocuments()
})
</script>

<template>
  <div class="library-page h-screen w-screen flex flex-col transition-colors duration-300" :class="{ 'dark': themeStore.isDarkMode }">
    <!-- Top Toolbar -->
    <header class="h-14 flex items-center justify-between px-6 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1e1e1e] z-10">
      <div class="flex items-center gap-4">
        <button @click="router.push('/')" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-600 dark:text-gray-400">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
        </button>
        <h1 class="text-xl font-bold text-gray-900 dark:text-white">文献库管理</h1>
      </div>

      <div class="flex items-center gap-3">
        <!-- Search bar -->
        <div class="relative w-64">
          <input 
            v-model="searchQuery"
            type="text" 
            placeholder="搜索文献标题..." 
            class="w-full pl-9 pr-4 py-1.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 dark:text-gray-300"
          />
          <svg class="w-4 h-4 absolute left-3 top-2.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        </div>

        <button 
          @click="handleZoteroImport" 
          :disabled="isImporting"
          class="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm transition-colors border border-gray-200 dark:border-gray-700"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14h-2v-4h2v4zm4 0h-2v-6h2v6zm-2-8c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1z"/></svg>
          {{ isImporting ? '导入中...' : 'Zotero 导入' }}
        </button>

        <button 
          @click="handleExportAll"
          :disabled="isExporting"
          class="flex items-center gap-2 px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
          {{ isExporting ? '导出中...' : '一键导出' }}
        </button>
      </div>
    </header>

    <!-- Main Content Body -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Folder Sidebar -->
      <aside class="w-56 bg-white dark:bg-[#1e1e1e] border-r border-gray-200 dark:border-gray-800 flex flex-col p-4 overflow-y-auto">
        <div class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">我的文献库</div>
        <nav class="space-y-1">
          <div 
            @click="selectFolder('all')"
            :class="[
              'flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all',
              selectedFolder === 'all' ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
            ]"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
            全部文献
          </div>
          <div class="h-4"></div>
          <div class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">分类标签</div>
          <div 
            v-for="folder in folders" 
            :key="folder"
            @click="selectFolder(folder)"
            :class="[
              'flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all group',
              selectedFolder === folder ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
            ]"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
            <span class="truncate flex-1">{{ folder }}</span>
          </div>
        </nav>
      </aside>

      <!-- Results Table Area -->
      <main class="flex-1 bg-gray-50 dark:bg-[#121212] overflow-y-auto p-6">
        <div class="bg-white dark:bg-[#1e1e1e] rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-gray-50/50 dark:bg-gray-900/50 border-b border-gray-200 dark:border-gray-800 text-sm font-semibold text-gray-600 dark:text-gray-400">
                <th class="w-10 px-4 py-3"></th>
                <th class="px-4 py-3">标题</th>
                <th class="w-24 px-4 py-3 text-center">页数</th>
                <th class="w-48 px-4 py-3">添加时间</th>
                <th class="w-48 px-4 py-3">标签分组</th>
                <th class="w-20 px-4 py-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="doc in filteredDocuments" :key="doc.id">
                <!-- Main Paper Row -->
                <tr 
                  @dblclick="openPaper(doc.id)"
                  class="group border-b border-gray-100 dark:border-gray-800/50 hover:bg-primary-50/30 dark:hover:bg-primary-900/5 text-sm transition-colors cursor-default"
                >
                  <td class="px-4 py-3 text-center">
                    <button 
                      @click="toggleExpand(doc.id)"
                      class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-transform duration-200"
                      :class="{ 'rotate-90': expandedPaperIds.has(doc.id) }"
                    >
                      <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                    </button>
                  </td>
                  <td class="px-4 py-3">
                    <div class="font-medium text-gray-900 dark:text-gray-200 hover:text-primary-600 dark:hover:text-primary-400 cursor-pointer" @click="openPaper(doc.id)">
                      {{ doc.name }}
                    </div>
                  </td>
                  <td class="px-4 py-3 text-center text-gray-500">{{ doc.pageCount || '-' }}</td>
                  <td class="px-4 py-3 text-gray-500 whitespace-nowrap">{{ formatDate(doc.uploadedAt) }}</td>
                  <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1.5 items-center">
                      <span 
                        v-for="tag in doc.tags" :key="tag"
                        class="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-md text-xs flex items-center gap-1 group/tag"
                      >
                        {{ tag }}
                        <button @click.stop="handleRemoveTag(doc.id, tag)" class="hover:text-red-500 opacity-0 group-hover/tag:opacity-100 transition-opacity">
                          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                      </span>
                      <div class="relative group/addtag">
                        <button class="p-1 text-gray-400 hover:text-primary-500 transition-colors">
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
                        </button>
                        <!-- Add Tag Popover (Enhanced with selection) -->
                        <div class="absolute left-0 bottom-full mb-2 opacity-0 group-focus-within/addtag:opacity-100 transition-opacity pointer-events-none group-focus-within/addtag:pointer-events-auto bg-white dark:bg-gray-800 shadow-xl border border-gray-200 dark:border-gray-700 rounded-lg p-2 z-20 w-48 flex flex-col gap-2">
                          <div class="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase px-1">添加标签</div>
                          <div class="flex gap-1">
                          <input 
                            v-model="newTagInputs[doc.id]"
                            @keyup.enter="handleAddTag(doc.id)"
                            type="text" 
                            placeholder="搜索或输入标签..." 
                            class="flex-1 text-xs px-2 py-1 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 dark:text-white"
                          />
                            <button @click="handleAddTag(doc.id)" class="text-[10px] bg-primary-600 hover:bg-primary-700 text-white px-2 py-1 rounded transition-colors flex-shrink-0">确定</button>
                          </div>
                          
                          <!-- Suggested existing tags -->
                          <div v-if="doc && getSuggestedTags(doc).length > 0" class="flex flex-col border-t border-gray-100 dark:border-gray-700 pt-1 mt-1 max-h-32 overflow-y-auto">
                            <div class="text-[9px] text-gray-400 dark:text-gray-500 mb-1 px-1">已有标签建议</div>
                            <div 
                              v-for="tag in (doc ? getSuggestedTags(doc) : [])" 
                              :key="tag"
                              @mousedown.prevent="handleAddTag(doc.id, tag)"
                              class="text-xs px-2 py-1 hover:bg-primary-50 dark:hover:bg-primary-900/20 text-gray-600 dark:text-gray-400 rounded cursor-pointer truncate transition-colors"
                            >
                              {{ tag }}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-center">
                    <button 
                      @click="openPaper(doc.id)" 
                      class="text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 px-2 py-1 rounded transition-colors"
                    >
                      阅读
                    </button>
                  </td>
                </tr>

                <!-- Expanded Notes Section -->
                <tr v-if="expandedPaperIds.has(doc.id)">
                  <td colspan="6" class="px-8 py-0 bg-gray-50/30 dark:bg-gray-900/10 overflow-hidden">
                    <div class="py-4 border-l-4 border-primary-500/30 pl-6 my-2 animate-slide-down">
                      <div v-if="loadingNotes[doc.id]" class="flex items-center gap-3 py-4 text-gray-500">
                        <div class="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                        <span>获取笔记中...</span>
                      </div>
                      <div v-else-if="libraryStore.notesCache[doc.id]?.length" class="space-y-3">
                        <div v-for="note in libraryStore.notesCache[doc.id]" :key="note.id" class="bg-white dark:bg-[#252526] p-4 rounded-lg border border-gray-100 dark:border-gray-800 shadow-sm relative group/note">
                          <div class="flex items-center justify-between mb-2">
                            <h4 class="font-semibold text-gray-800 dark:text-gray-200 truncate pr-10">{{ note.title || '无标题笔记' }}</h4>
                            <span class="text-[10px] px-1.5 py-0.5 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 rounded">笔记</span>
                          </div>
                          <div class="text-sm text-gray-600 dark:text-gray-400 line-clamp-3 mb-3 leading-relaxed">
                            {{ note.content }}
                          </div>
                          <div class="flex flex-wrap gap-2">
                            <span v-for="keyword in note.keywords" :key="keyword" class="text-[10px] bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full">
                              #{{ keyword }}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div v-else class="py-10 text-center">
                        <div class="text-gray-400 text-sm mb-2">该文献暂无笔记</div>
                        <button @click="openPaper(doc.id)" class="text-xs text-primary-600 dark:text-primary-400 hover:underline">点击进入阅读器添加笔记</button>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
              <!-- Empty Search Results -->
              <tr v-if="filteredDocuments.length === 0">
                <td colspan="6" class="py-20 text-center">
                  <div class="text-gray-400 flex flex-col items-center gap-3">
                    <svg class="w-16 h-16 opacity-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
                    <p>未找到匹配的文献</p>
                    <button v-if="searchQuery" @click="searchQuery = ''" class="text-primary-500 hover:underline mt-2">清除搜索条件</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.library-page {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

@keyframes slide-down {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-slide-down {
  animation: slide-down 0.3s ease-out;
}

/* Custom scrollbar for Zotero feel */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.2);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.4);
}

.dark ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
