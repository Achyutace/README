<script setup lang="ts">
import { ref, watch } from 'vue'
import { useLibraryStore } from '../../stores/library'

const libraryStore = useLibraryStore()
const notesContent = ref('')

// Load notes when document changes
watch(() => libraryStore.currentDocument?.id, (newId) => {
  if (newId) {
    // Load saved notes for this document (if any)
    const savedNotes = localStorage.getItem(`notes-${newId}`)
    notesContent.value = savedNotes || ''
  } else {
    notesContent.value = ''
  }
}, { immediate: true })

// Auto-save notes
let saveTimeout: number | null = null
watch(notesContent, (newContent) => {
  if (saveTimeout) {
    clearTimeout(saveTimeout)
  }
  saveTimeout = setTimeout(() => {
    if (libraryStore.currentDocument?.id) {
      localStorage.setItem(`notes-${libraryStore.currentDocument.id}`, newContent)
    }
  }, 500) as unknown as number
})
</script>

<template>
  <div class="h-full flex flex-col bg-white dark:bg-[#1e1e1e]">
    <textarea
      v-model="notesContent"
      class="flex-1 w-full p-4 resize-none border-none outline-none bg-transparent text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 font-mono text-sm leading-relaxed"
      placeholder="在这里记录你的笔记..."
    ></textarea>
  </div>
</template>
