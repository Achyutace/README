<script setup lang="ts">
import LibrarySidebar from './components/sidebar/LibrarySidebar.vue'
import PdfViewer from './components/pdf/PdfViewer.vue'
import AiPanel from './components/ai-panel/AiPanel.vue'
import { useLibraryStore } from './stores/library'
import { useAiStore } from './stores/ai'

const libraryStore = useLibraryStore()
const aiStore = useAiStore()
</script>

<template>
  <div class="flex h-screen w-screen bg-gray-50">
    <!-- Left Sidebar - Library -->
    <LibrarySidebar class="flex-shrink-0" />

    <!-- Main Content Area -->
    <main class="flex flex-1 overflow-hidden">
      <!-- PDF Viewer -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <PdfViewer />
      </div>

      <!-- Right Panel - AI Assistant -->
      <AiPanel
        v-if="libraryStore.currentDocument"
        :class="{ 'w-0': aiStore.isPanelCollapsed }"
        class="flex-shrink-0 transition-all duration-300"
      />
    </main>
  </div>
</template>
