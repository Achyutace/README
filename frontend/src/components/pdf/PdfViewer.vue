<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'
import { useLibraryStore } from '../../stores/library'
import PdfToolbar from './PdfToolbar.vue'
import TextSelectionTooltip from './TextSelectionTooltip.vue'
import VuePdfEmbed from 'vue-pdf-embed'

const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

const containerRef = ref<HTMLElement | null>(null)
const pdfRef = ref<InstanceType<typeof VuePdfEmbed> | null>(null)

const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

function handleLoaded(pdf: any) {
  if (pdf && pdf.numPages) {
    pdfStore.setTotalPages(pdf.numPages)
    if (libraryStore.currentDocumentId) {
      libraryStore.updateDocumentPageCount(libraryStore.currentDocumentId, pdf.numPages)
    }
  }
}

function handleTextSelection() {
  const selection = window.getSelection()
  if (selection && selection.toString().trim()) {
    const text = selection.toString().trim()
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()

    pdfStore.setSelectedText(text, {
      x: rect.left + rect.width / 2,
      y: rect.top - 10
    })

    tooltipPosition.value = {
      x: rect.left + rect.width / 2,
      y: rect.top - 10
    }
    showTooltip.value = true
  }
}

function handleClickOutside() {
  showTooltip.value = false
  pdfStore.clearSelection()
}

function handleScroll() {
  if (containerRef.value && pdfRef.value) {
    const container = containerRef.value
    const scrollTop = container.scrollTop
    const pageHeight = container.scrollHeight / pdfStore.totalPages
    const currentPage = Math.floor(scrollTop / pageHeight) + 1
    if (currentPage !== pdfStore.currentPage && currentPage <= pdfStore.totalPages) {
      pdfStore.goToPage(currentPage)
    }
  }
}

watch(() => pdfStore.currentPage, (newPage) => {
  if (containerRef.value && pdfStore.totalPages > 0) {
    const pageHeight = containerRef.value.scrollHeight / pdfStore.totalPages
    containerRef.value.scrollTo({
      top: (newPage - 1) * pageHeight,
      behavior: 'smooth'
    })
  }
})
</script>

<template>
  <div class="flex flex-col h-full bg-gray-100">
    <!-- Toolbar -->
    <PdfToolbar />

    <!-- PDF Content -->
    <div
      v-if="pdfStore.currentPdfUrl"
      ref="containerRef"
      class="flex-1 overflow-auto p-4"
      @mouseup="handleTextSelection"
      @click="handleClickOutside"
      @scroll="handleScroll"
    >
      <div class="max-w-4xl mx-auto bg-white shadow-lg">
        <VuePdfEmbed
          ref="pdfRef"
          :source="pdfStore.currentPdfUrl"
          :scale="pdfStore.scale"
          @loaded="handleLoaded"
          class="pdf-viewer"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else
      class="flex-1 flex flex-col items-center justify-center text-gray-400"
    >
      <svg class="w-24 h-24 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h2 class="text-xl font-medium mb-2">开始阅读</h2>
      <p class="text-sm">从左侧上传 PDF 文件开始您的阅读之旅</p>
    </div>

    <!-- Text Selection Tooltip -->
    <TextSelectionTooltip
      v-if="showTooltip && pdfStore.selectedText"
      :position="tooltipPosition"
      :text="pdfStore.selectedText"
      @close="handleClickOutside"
    />
  </div>
</template>

<style scoped>
.pdf-viewer {
  width: 100%;
}

.pdf-viewer :deep(canvas) {
  display: block;
  margin: 0 auto;
}
</style>
