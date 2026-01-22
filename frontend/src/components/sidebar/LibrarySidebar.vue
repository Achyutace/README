<script setup lang="ts">
import { ref } from 'vue'
import { useLibraryStore } from '../../stores/library'
import { usePdfStore } from '../../stores/pdf'
import { useAiStore } from '../../stores/ai'

const libraryStore = useLibraryStore()
const pdfStore = usePdfStore()
const aiStore = useAiStore()

const isCollapsed = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function toggleSidebar() {
  isCollapsed.value = !isCollapsed.value
}

function triggerFileUpload() {
  fileInput.value?.click()
}

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    const file = files[0]
    if (file && file.type === 'application/pdf') {
      try {
        const doc = await libraryStore.addDocument(file)
        libraryStore.selectDocument(doc.id)
        pdfStore.setCurrentPdf(doc.url, doc.id) // 传递文档ID
        aiStore.resetForNewDocument()
      } catch (error) {
        alert('上传失败，请确保后端服务已启动')
      }
    }
  }
  target.value = ''
}

function selectDocument(id: string) {
  const doc = libraryStore.documents.find((d: { id: string }) => d.id === id)
  if (doc) {
    libraryStore.selectDocument(id)
    pdfStore.setCurrentPdf(doc.url, doc.id) // 传递文档ID
    aiStore.resetForNewDocument()
  }
}

function removeDocument(id: string, event: Event) {
  event.stopPropagation()
  pdfStore.removeDocumentHighlights(id) // 删除文档时清理对应的高亮
  libraryStore.removeDocument(id)
}
</script>

<template>
  <aside
    :class="[
      'h-full bg-sidebar text-white flex flex-col transition-all duration-300',
      isCollapsed ? 'w-16' : 'w-60'
    ]"
  >
    <!-- Logo Area -->
    <div class="p-4 flex items-center justify-between border-b border-gray-700">
      <h1 v-if="!isCollapsed" class="text-xl font-bold text-primary-500">
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
        <span v-if="!isCollapsed">上传 PDF</span>
      </button>
    </div>

    <!-- Document List -->
    <div class="flex-1 overflow-y-auto px-2">
      <div v-if="!isCollapsed" class="px-2 py-2 text-xs text-gray-400 uppercase tracking-wider">
        文献库
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
          <span v-if="!isCollapsed" class="flex-1 truncate text-sm">
            {{ doc.name }}
          </span>
          <button
            v-if="!isCollapsed"
            @click="removeDocument(doc.id, $event)"
            class="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-600/20 rounded transition-all"
          >
            <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </li>
      </ul>

      <!-- Empty State -->
      <div
        v-if="libraryStore.documents.length === 0 && !isCollapsed"
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
          <span class="text-sm font-medium">U</span>
        </div>
        <div v-if="!isCollapsed" class="flex-1">
          <p class="text-sm font-medium">用户</p>
        </div>
      </div>
    </div>
  </aside>
</template>
