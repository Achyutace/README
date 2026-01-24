<script setup lang="ts">
// ------------------------- 导入依赖与笔记管理 -------------------------
// 引入 Vue 响应式 API、文库 store 与笔记 API，以及内部编辑器组件
import { ref, watch, nextTick } from 'vue'
import { useLibraryStore } from '../../stores/library'
import { notesApi, type Note } from '../../api'
import NoteEditor from './NoteEditor.vue'

interface NoteCard {
  id: string | number  // 可以是本地临时ID（string）或数据库ID（number）
  title: string
  content: string
  isEditing: boolean
  isCollapsed: boolean
  showRawMd?: boolean
  createdAt: number
  isLocal?: boolean  // 标记是否为本地临时笔记（未保存到数据库）
}

const libraryStore = useLibraryStore()
const cards = ref<NoteCard[]>([])
const isLoading = ref(false)
const containerRef = ref<HTMLElement | null>(null)

// Generate unique ID for temporary notes
function generateTempId() {
  return `temp-${Date.now()}-${Math.random().toString(36).substring(2)}`
}

// Load notes from database when document changes
async function loadNotesFromDB() {
  if (!libraryStore.currentDocument?.id) {
    cards.value = []
    return
  }
  
  isLoading.value = true
  try {
    const response = await notesApi.getNotes(libraryStore.currentDocument.id)
    cards.value = response.notes.map((note: Note) => ({
      id: note.id,
      title: note.title || '',
      content: note.content || '',
      isEditing: false,
      isCollapsed: false,
      showRawMd: false,
      createdAt: new Date(note.created_time).getTime(),
      isLocal: false
    }))
  } catch (error) {
    console.error('Failed to load notes from database:', error)
    cards.value = []
  } finally {
    isLoading.value = false
  }
}

// Watch document changes and load notes
watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    loadNotesFromDB()
  } else {
    cards.value = []
  }
}, { immediate: true })

// Save note to database
async function saveNoteToDB(card: NoteCard) {
  if (!libraryStore.currentDocument?.id) return
  
  try {
    if (card.isLocal) {
      // 新建笔记
      const response = await notesApi.createNote({
        pdfId: libraryStore.currentDocument.id,
        title: card.title,
        content: card.content
      })
      // 更新卡片ID为数据库ID
      card.id = response.id
      card.isLocal = false
    } else if (typeof card.id === 'number') {
      // 更新现有笔记
      await notesApi.updateNote(card.id, {
        title: card.title,
        content: card.content
      })
    }
  } catch (error) {
    console.error('Failed to save note to database:', error)
    throw error
  }
}

// Add new card (temporary, will be saved to DB when editing is done)
function addCard() {
  const newCard: NoteCard = {
    id: generateTempId(),
    title: '',
    content: '',
    isEditing: true,
    isCollapsed: false,
    showRawMd: false,
    createdAt: Date.now(),
    isLocal: true
  }
  cards.value.push(newCard)
  nextTick(() => {
    containerRef.value?.scrollTo({ top: containerRef.value.scrollHeight, behavior: 'smooth' })
  })
}

// Delete card from database and local state
async function deleteCard(id: string | number) {
  // 如果是数据库笔记，先删除数据库中的记录
  if (typeof id === 'number') {
    try {
      await notesApi.deleteNote(id)
    } catch (error) {
      console.error('Failed to delete note from database:', error)
      return
    }
  }
  // 从本地状态中移除
  cards.value = cards.value.filter(c => c.id !== id)
}

// Toggle edit mode and save when exiting edit mode
async function toggleEdit(card: NoteCard) {
  const wasEditing = card.isEditing
  card.isEditing = !card.isEditing
  
  // 如果退出编辑模式，保存到数据库
  if (wasEditing && !card.isEditing) {
    try {
      await saveNoteToDB(card)
    } catch (error) {
      // 保存失败，恢复编辑模式
      card.isEditing = true
    }
  }
}

// Toggle collapse state (no need to save to DB)
function toggleCollapse(card: NoteCard, event: Event) {
  event.stopPropagation()
  card.isCollapsed = !card.isCollapsed
}

// Toggle raw markdown view (no need to save to DB)
function toggleRawMd(card: NoteCard) {
  card.showRawMd = !card.showRawMd
}

// Update card (just update local state, no auto-save)
// Saving happens when exiting edit mode via toggleEdit
function updateCard() {
  // 仅更新本地状态，不触发保存
  // 保存会在退出编辑模式时通过 toggleEdit 触发
}

// Get first line of content
function getFirstLine(text: string): string {
  if (!text) return ''
  // 移除 markdown 符号取纯文本预览
  const cleanText = text.replace(/[#*`]/g, '') 
  const firstLine = cleanText.split('\n')[0] || ''
  return firstLine
}

// Auto resize textarea
function autoResize(target: HTMLTextAreaElement) {
  target.style.height = 'auto'
  target.style.height = target.scrollHeight + 'px'
}

// Directive to adjust height on mount
const vAutoHeight = {
  mounted: (el: HTMLTextAreaElement) => autoResize(el),
  updated: (el: HTMLTextAreaElement) => autoResize(el)
}

// Handle textarea input
function handleInput(event: Event) {
  updateCard()
  autoResize(event.target as HTMLTextAreaElement)
}

// Expose addCard for parent component
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
              <div class="flex-1 px-3 text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                {{ card.title || '无标题' }}
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

<style scoped>
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
  
  /* Tiptap 特有的选中样式 */
  .ProseMirror-selectednode {
    @apply outline outline-2 outline-blue-500;
  }

  /* 只读模式下隐藏光标 */
  .ProseMirror[contenteditable="false"] {
    @apply cursor-default;
  }
}
</style>
