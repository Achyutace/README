<script setup lang="ts">
/**
 * NotesPanel.vue
 * 说明：该文件实现笔记列表（卡片式）的显示、编辑、创建与删除逻辑。
 * - 支持在当前打开的文档（PDF）下加载并展示笔记
 * - 支持本地临时笔记（未保存）与数据库中持久笔记的混合管理
 * - 编辑时可使用富文本/渲染模式（NoteEditor）或源码（Raw Markdown）模式
 */

// ------------------------- 导入与初始化 -------------------------
// 使用 Vue 的 Composition API
import { ref, watch, nextTick } from 'vue'
// 引入应用级的 store，用于获取当前文档（pdf）信息
import { useLibraryStore } from '../../stores/library'
// 与后端交互的笔记 API 和类型定义
import { notesApi, type Note } from '../../api'
// 内部使用的编辑器组件（基于 Tiptap）
import NoteEditor from './NoteEditor.vue'

// ------------------------- 数据类型定义（TypeScript） -------------------------
/**
 * NoteCard
 * - 用于在 UI 中表示一条笔记卡片的数据结构
 * - id 可以是数据库自增 ID（number）或本地临时 ID（string）
 */
interface NoteCard {
  id: string | number  // 本地临时ID（string，如 temp-...）或数据库ID（number）
  title: string        // 笔记标题
  content: string      // 笔记正文（Markdown）
  keywords: string[]   // 笔记关键词列表
  isEditing: boolean   // 是否处于编辑模式
  isCollapsed: boolean // 在已完成（非编辑）状态下是否折叠显示只读预览
  showRawMd?: boolean  // 编辑模式下是否显示原始 Markdown 文本编辑器
  createdAt: number    // 创建时间的时间戳（用于 UI 排序或展示）
  isLocal?: boolean    // 是否为本地临时笔记（尚未保存到后端）
}

// ------------------------- 响应式状态 -------------------------
const libraryStore = useLibraryStore()        // 读取当前文档 id 等信息
const cards = ref<NoteCard[]>([])             // 卡片列表（UI 数据源）
const isLoading = ref(false)                 // 加载状态（用于展示加载动画等）
const containerRef = ref<HTMLElement | null>(null) // 卡片列表容器的 DOM 引用（用于滚动）

// ------------------------- 工具函数 -------------------------
/**
 * 生成临时 ID
 * 用于本地新建的笔记，在保存到后端前用字符串 ID 占位
 */
function generateTempId() {
  return `temp-${Date.now()}-${Math.random().toString(36).substring(2)}`
}

// ------------------------- 与后端交互：加载笔记 -------------------------
/**
 * 从数据库加载当前文档对应的笔记列表，并转换为 NoteCard
 * - 当没有 currentDocument 时清空 cards
 * - 捕获并打印错误以便查错
 */
async function loadNotesFromDB() {
  if (!libraryStore.currentDocument?.id) {
    cards.value = []
    return
  }
  
  isLoading.value = true
  try {
    // 请求后端 API：根据当前文档 id 获取笔记
    const response = await notesApi.getNotes(libraryStore.currentDocument.id)
    // 将后端返回的 Note 转换为 UI 使用的 NoteCard 格式
    cards.value = response.notes.map((note: Note) => ({
      id: note.id,
      title: note.title || '',
      content: note.content || '',
      keywords: note.keywords || [],
      isEditing: false,
      isCollapsed: false,
      showRawMd: false,
      createdAt: new Date(note.createdAt).getTime(),
      isLocal: false
    }))
  } catch (error) {
    // 加载失败时清空并打印错误，避免残留旧数据影响展示
    console.error('Failed to load notes from database:', error)
    cards.value = []
  } finally {
    isLoading.value = false
  }
}

// ------------------------- 监听：文档切换时刷新笔记 -------------------------
/**
 * 监听当前文档的 id 变化
 * - newId 存在时加载对应笔记
 * - 否则清空笔记列表
 * - immediate: true 确保组件初始化时立即执行一次
 */
watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    loadNotesFromDB()
  } else {
    cards.value = []
  }
}, { immediate: true })

// ------------------------- 保存到后端 -------------------------
/**
 * 保存笔记到数据库
 * - 如果 card.isLocal 为 true：创建笔记并替换临时 id
 * - 否则（存在数据库 id 的情况）进行更新
 * - 抛出异常由调用方处理（例如恢复编辑状态）
 */
async function saveNoteToDB(card: NoteCard) {
  if (!libraryStore.currentDocument?.id) return
  
  try {
    if (card.isLocal) {
      // 新建笔记：发送 pdfId、title、content、keywords
      const response = await notesApi.createNote({
        pdfId: libraryStore.currentDocument.id,
        title: card.title,
        content: card.content,
        keywords: card.keywords
      })
      // 将本地临时 ID 更新为后端返回的数据库 ID，并标记为已持久化
      card.id = response.id
      card.isLocal = false
    } else if (typeof card.id === 'number') {
      // 更新笔记
      await notesApi.updateNote(card.id, {
        title: card.title,
        content: card.content,
        keywords: card.keywords
      })
    }
  } catch (error) {
    // 上层调用会根据异常恢复编辑状态或提示用户
    console.error('Failed to save note to database:', error)
    throw error
  }
}

// ------------------------- 新建与删除 -------------------------
/**
 * 新增临时卡片（处于编辑状态）
 * - 仅在 UI 层创建本地记录，保存时再写入后端
 * - 新建后自动滚动到底部以方便继续输入
 */
function addCard() {
  const newCard: NoteCard = {
    id: generateTempId(),
    title: '',
    content: '',
    keywords: [],
    isEditing: true,
    isCollapsed: false,
    showRawMd: false,
    createdAt: Date.now(),
    isLocal: true
  }
  cards.value.push(newCard)
  nextTick(() => {
    // 平滑滚动至容器底部，提升 UX
    containerRef.value?.scrollTo({ top: containerRef.value.scrollHeight, behavior: 'smooth' })
  })
}

// ------------------------- 删除卡片 -------------------------
async function deleteCard(id: string | number) {
  if (typeof id === 'number') {
    try {
      await notesApi.deleteNote(id)
    } catch (error) {
      console.error('Failed to delete note from database:', error)
      return
    }
  }
  // 本地状态移除卡片
  cards.value = cards.value.filter(c => c.id !== id)
}

// ------------------------- 编辑状态切换与保存 -------------------------
/**
 * 切换编辑模式
 * - 从编辑->非编辑时触发保存操作（保存失败则恢复为编辑模式）
 */
async function toggleEdit(card: NoteCard) {
  const wasEditing = card.isEditing
  card.isEditing = !card.isEditing
  
  if (wasEditing && !card.isEditing) {
    try {
      await saveNoteToDB(card)
    } catch (error) {
      // 保存失败时恢复编辑，避免用户丢失输入
      card.isEditing = true
    }
  }
}

// ------------------------- UI 小工具 -------------------------
/**
 * 切换折叠状态（只影响 UI 展示，无需持久化）
 */
function toggleCollapse(card: NoteCard, event: Event) {
  // 阻止冒泡，避免触发卡片的整体点击（切换到编辑）
  event.stopPropagation()
  card.isCollapsed = !card.isCollapsed
}

/**
 * 切换源码模式（编辑时在 Markdown 文本框与富文本渲染器之间切换）
 */
function toggleRawMd(card: NoteCard) {
  card.showRawMd = !card.showRawMd
}

/**
 * 本函数仅用于触发本地状态更新（例如 v-model 双向绑定时调用）
 * 真正的持久化保存在退出编辑时触发
 */
function updateCard() {
  // 仅更新本地状态，不触发保存
}

/**
 * 获取文本的首行（用于折叠时显示摘要）
 * - 移除一些常见的 Markdown 标记作为简化的预览
 */
function getFirstLine(text: string): string {
  if (!text) return ''
  const cleanText = text.replace(/[#*`]/g, '') 
  const firstLine = cleanText.split('\n')[0] || ''
  return firstLine
}

// ------------------------- 关键词管理 -------------------------
/**
 * 添加关键词
 * 按回车时触发，将输入的关键词添加到卡片
 */
function addKeyword(card: NoteCard, event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.value.trim()
  if (value && !card.keywords.includes(value)) {
    card.keywords.push(value)
  }
  input.value = ''
}

/**
 * 移除关键词
 */
function removeKeyword(card: NoteCard, index: number) {
  card.keywords.splice(index, 1)
}

// ------------------------- 文本域自适应高度 -------------------------
function autoResize(target: HTMLTextAreaElement) {
  target.style.height = 'auto'
  target.style.height = target.scrollHeight + 'px'
}

// 指令：在 mounted / updated 时自动调整高度
const vAutoHeight = {
  mounted: (el: HTMLTextAreaElement) => autoResize(el),
  updated: (el: HTMLTextAreaElement) => autoResize(el)
}

// 文本框输入处理：更新本地状态并自适应高度
function handleInput(event: Event) {
  updateCard()
  autoResize(event.target as HTMLTextAreaElement)
}

// 将 addCard 暴露给父组件（如侧栏或工具条调用新建功能）
defineExpose({ addCard })
</script>

<template>
  <div class="h-full flex flex-col bg-white dark:bg-[#2d2d30]">
    <!-- Cards Container -->
    <div ref="containerRef" class="flex-1 overflow-y-auto pb-2 pt-0 space-y-1">
      <!-- Empty State -->
      <div v-if="cards.length === 0" class="flex items-center justify-center h-full">
        
      </div>

      <!-- Card List -->
      <div
        v-for="card in cards"
        :key="card.id"
        class="bg-white dark:bg-[#2d2d30] border-t border-b-0 border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        <!-- Editing Mode -->
        <template v-if="card.isEditing">
          <!-- Header with action buttons -->
          <div class="py-2 flex items-center justify-between">
            <input
              v-model="card.title"
              @input="updateCard"
              type="text"
              placeholder="标题"
              class="flex-1 px-3 py-1 text-base font-medium bg-transparent border-none outline-none text-gray-800 dark:text-gray-200 placeholder-gray-400"
            />
            <div class="flex items-center gap-1 mr-2">
              <!-- Toggle Raw MD -->
              <button
                @click="toggleRawMd(card)"
                class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                :class="{ 'text-primary-500 bg-primary-50 dark:bg-primary-900/20': card.showRawMd, 'text-gray-400': !card.showRawMd }"
                :title="card.showRawMd ? '切换渲染模式' : '切换源码模式'"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </button>
              <!-- Delete Button -->
              <button
                @click="deleteCard(card.id)"
                class="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                title="删除"
              >
                <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
              <!-- Done Button -->
              <button
                @click="toggleEdit(card)"
                class="p-1 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded transition-colors"
                title="完成"
              >
                <svg class="w-4 h-4 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              </button>
            </div>
          </div>
          <div class="py-0 px-3">
            <div class="border-t border-gray-100 dark:border-gray-700 w-1/4"></div>
          </div>
          <!-- Keywords Input -->
          <div class="py-2 px-3">
            <div class="flex flex-wrap items-center gap-2">
              <span 
                v-for="(keyword, index) in card.keywords" 
                :key="index"
                class="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full"
              >
                {{ keyword }}
                <button
                  @click="removeKeyword(card, index)"
                  class="ml-1 hover:text-primary-900 dark:hover:text-primary-100"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
              <input
                type="text"
                placeholder="添加关键词，回车确认"
                @keyup.enter="addKeyword(card, $event)"
                class="flex-1 min-w-[120px] text-xs bg-transparent border-none outline-none text-gray-600 dark:text-gray-400 placeholder-gray-400"
              />
            </div>
          </div>
          <div class="py-0 px-3">
            <div class="border-t border-gray-100 dark:border-gray-700 w-full"></div>
          </div>
          <div class="py-2 px-3">
            <textarea
              v-if="card.showRawMd"
              v-model="card.content"
              v-auto-height
              @input="handleInput"
              class="w-full text-sm font-mono bg-transparent border-none outline-none focus:ring-0 resize-none text-gray-800 dark:text-gray-200 p-0 overflow-hidden block"
              placeholder="输入 Markdown 内容..."
              spellcheck="false"
            ></textarea>
            <!-- 使用 Tiptap 编辑器，提供 Markdown 即时渲染 -->
            <NoteEditor
              v-else
              v-model="card.content"
              :editable="true"
              @update:modelValue="updateCard"
            />
          </div>
        </template>

        <!-- Completed Mode -->
        <template v-else>
          <div
            class="cursor-pointer hover:bg-gray-50 dark:hover:bg-[#363636] transition-colors"
            @click="toggleEdit(card)"
          >
            <div class="py-2 flex items-center justify-between">
              <div class="flex-1 px-3">
                <div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                  {{ card.title || '无标题' }}
                </div>
                <!-- Keywords Display -->
                <div v-if="card.keywords.length > 0" class="flex flex-wrap gap-1 mt-1">
                  <span 
                    v-for="(keyword, index) in card.keywords" 
                    :key="index"
                    class="inline-block px-1.5 py-0.5 text-[10px] bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded"
                  >
                    {{ keyword }}
                  </span>
                </div>
              </div>
              <div class="flex items-center">
                <!-- Delete Button -->
                <button
                  @click.stop="deleteCard(card.id)"
                  class="p-1 mr-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
                  title="删除"
                >
                  <svg class="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
                <!-- Collapse/Expand Button -->
                <button
                  @click="toggleCollapse(card, $event)"
                  class="px-2 py-1 mr-1 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                  :title="card.isCollapsed ? '展开' : '折叠'"
                >
                  <svg
                    class="w-4 h-4 text-gray-500 dark:text-gray-400 transition-transform"
                    :class="{ 'rotate-180': !card.isCollapsed }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
            </div>
            <div class="px-3 pb-2 border-b-0">
              <!-- Collapsed: show only first line -->
              <div
                v-if="card.isCollapsed"
                class="text-sm text-gray-600 dark:text-gray-400 truncate"
              >
                {{ getFirstLine(card.content) || '无内容' }}
              </div>
              <!-- Expanded: show rendered content using Tiptap in read-only mode -->
              <div v-else class="text-sm text-gray-600 dark:text-gray-400">
                <NoteEditor
                  v-model="card.content"
                  :editable="false"
                  @update:modelValue="updateCard"
                />
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped lang="postcss">
/* 
  Tiptap 编辑器的 Markdown 渲染样式
  通过 :deep() 深度选择器作用到 NoteEditor 组件内部
*/
:deep(.markdown-content) {
  /* 基础字体设置 */
  @apply text-sm text-gray-500 dark:text-gray-400;

  h1, h2, h3, h4, h5, h6 {
    @apply font-semibold text-gray-800 dark:text-gray-100 mt-3 mb-1 first:mt-0;
  }
  h1 { @apply text-lg; }
  h2 { @apply text-base; }
  h3 { @apply text-sm; }

  p { @apply my-1 leading-relaxed first:mt-0 last:mb-0; }

  ul, ol { @apply pl-5 my-1 last:mb-0; }
  ul { @apply list-disc; }
  ol { @apply list-decimal; }
  li { @apply my-0.5; }

  code {
    @apply px-1 py-0.5 bg-gray-100 dark:bg-gray-700 text-xs rounded font-mono text-pink-500;
  }

  pre {
    @apply bg-gray-100 dark:bg-gray-800 p-2 rounded my-2 overflow-x-auto;
  }
  pre code {
    @apply bg-transparent p-0 text-gray-800 dark:text-gray-200;
  }

  blockquote {
    @apply border-l-4 border-gray-300 dark:border-gray-600 pl-2 my-2 text-gray-500 italic;
  }

  a {
    @apply text-blue-600 dark:text-blue-400 hover:underline cursor-pointer;
  }
  
  .ProseMirror-selectednode {
    @apply outline outline-2 outline-blue-500;
  }

  .ProseMirror[contenteditable="false"] {
    @apply cursor-default;
  }
}
</style>
