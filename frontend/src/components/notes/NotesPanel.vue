<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useLibraryStore } from '../../stores/library'

interface NoteCard {
  id: string
  title: string
  content: string
  isEditing: boolean
  createdAt: number
}

const libraryStore = useLibraryStore()
const cards = ref<NoteCard[]>([])

// Generate unique ID
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2)
}

// Load cards when document changes
watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    const savedCards = localStorage.getItem(`note-cards-${newId}`)
    cards.value = savedCards ? JSON.parse(savedCards) : []
  } else {
    cards.value = []
  }
}, { immediate: true })

// Auto-save cards
function saveCards() {
  if (libraryStore.currentDocument?.id) {
    localStorage.setItem(`note-cards-${libraryStore.currentDocument.id}`, JSON.stringify(cards.value))
  }
}

// Add new card
function addCard() {
  const newCard: NoteCard = {
    id: generateId(),
    title: '',
    content: '',
    isEditing: true,
    createdAt: Date.now()
  }
  cards.value.unshift(newCard)
  saveCards()
}

// Delete card
function deleteCard(id: string) {
  cards.value = cards.value.filter(c => c.id !== id)
  saveCards()
}

// Toggle edit mode
function toggleEdit(card: NoteCard) {
  card.isEditing = !card.isEditing
  saveCards()
}

// Update card and save
function updateCard() {
  saveCards()
}

// Simple markdown renderer (basic support, no bold/italic)
function renderMarkdown(text: string): string {
  if (!text) return ''

  return text
    // Headers (H1 slightly larger, not drastically)
    .replace(/^### (.+)$/gm, '<div class="text-sm font-medium text-gray-700 dark:text-gray-300 mt-2 mb-1">$1</div>')
    .replace(/^## (.+)$/gm, '<div class="text-sm font-medium text-gray-700 dark:text-gray-300 mt-2 mb-1">$1</div>')
    .replace(/^# (.+)$/gm, '<div class="text-base font-medium text-gray-800 dark:text-gray-200 mt-2 mb-1">$1</div>')
    // Code blocks
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">$1</code>')
    // Line breaks
    .replace(/\n/g, '<br>')
}
</script>

<template>
  <div class="h-full flex flex-col bg-gray-100 dark:bg-[#1a1a1a]">
    <!-- Header with Add Button -->
    <div class="px-3 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-[#252526] flex items-center justify-between">
      <span class="text-xs text-gray-500 dark:text-gray-400">{{ cards.length }} 张卡片</span>
      <button
        @click="addCard"
        class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        title="添加卡片"
      >
        <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>

    <!-- Cards Container -->
    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      <!-- Empty State -->
      <div v-if="cards.length === 0" class="flex items-center justify-center h-full">
        <div class="text-center">
          <p class="text-sm text-gray-400 dark:text-gray-500 mb-2">暂无笔记卡片</p>
          <button
            @click="addCard"
            class="text-xs text-primary-500 hover:text-primary-600 dark:text-primary-400"
          >
            + 添加第一张卡片
          </button>
        </div>
      </div>

      <!-- Card List -->
      <div
        v-for="card in cards"
        :key="card.id"
        class="bg-white dark:bg-[#2d2d30] rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        <!-- Editing Mode -->
        <template v-if="card.isEditing">
          <div class="p-2">
            <input
              v-model="card.title"
              @input="updateCard"
              type="text"
              placeholder="标题"
              class="w-full px-2 py-1 text-sm font-medium bg-gray-50 dark:bg-[#1e1e1e] border border-gray-200 dark:border-gray-600 rounded outline-none focus:border-primary-400 text-gray-800 dark:text-gray-200 placeholder-gray-400"
            />
          </div>
          <div class="border-t border-gray-100 dark:border-gray-700"></div>
          <div class="p-2">
            <textarea
              v-model="card.content"
              @input="updateCard"
              placeholder="内容（支持 Markdown）"
              rows="4"
              class="w-full px-2 py-1 text-sm bg-gray-50 dark:bg-[#1e1e1e] border border-gray-200 dark:border-gray-600 rounded outline-none focus:border-primary-400 resize-none text-gray-700 dark:text-gray-300 placeholder-gray-400"
            ></textarea>
          </div>
          <div class="px-2 pb-2 flex justify-end gap-1">
            <button
              @click="deleteCard(card.id)"
              class="px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
            >
              删除
            </button>
            <button
              @click="toggleEdit(card)"
              class="px-2 py-1 text-xs text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded transition-colors"
            >
              完成
            </button>
          </div>
        </template>

        <!-- Completed Mode -->
        <template v-else>
          <div
            class="cursor-pointer hover:bg-gray-50 dark:hover:bg-[#363636] transition-colors"
            @click="toggleEdit(card)"
          >
            <div class="px-3 py-2">
              <div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                {{ card.title || '无标题' }}
              </div>
            </div>
            <div class="border-t border-gray-100 dark:border-gray-700"></div>
            <div class="px-3 py-2">
              <div
                class="text-xs text-gray-600 dark:text-gray-400 line-clamp-3"
                v-html="renderMarkdown(card.content) || '<span class=\'text-gray-400\'>无内容</span>'"
              ></div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
