<script setup lang="ts">
import { ref } from 'vue'
import { usePdfStore } from '../../stores/pdf'

const pdfStore = usePdfStore()
const pageInput = ref('')

function handlePageInput() {
  const page = parseInt(pageInput.value)
  if (!isNaN(page)) {
    pdfStore.goToPage(page)
  }
  pageInput.value = ''
}
</script>

<template>
  <div class="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
    <!-- Left: Zoom Controls -->
    <div class="flex items-center gap-2">
      <button
        @click="pdfStore.zoomOut"
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        title="缩小"
      >
        <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
        </svg>
      </button>
      <span class="text-sm font-medium text-gray-700 min-w-[4rem] text-center">
        {{ pdfStore.scalePercent }}%
      </span>
      <button
        @click="pdfStore.zoomIn"
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        title="放大"
      >
        <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>

    <!-- Center: Page Navigation -->
    <div class="flex items-center gap-2">
      <button
        @click="pdfStore.prevPage"
        :disabled="pdfStore.currentPage <= 1"
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="上一页"
      >
        <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      <div class="flex items-center gap-1">
        <input
          v-model="pageInput"
          type="text"
          :placeholder="String(pdfStore.currentPage)"
          @keyup.enter="handlePageInput"
          class="w-12 px-2 py-1 text-center text-sm border border-gray-300 rounded focus:outline-none focus:border-primary-500"
        />
        <span class="text-sm text-gray-500">/</span>
        <span class="text-sm text-gray-700">{{ pdfStore.totalPages || '-' }}</span>
      </div>

      <button
        @click="pdfStore.nextPage"
        :disabled="pdfStore.currentPage >= pdfStore.totalPages"
        class="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="下一页"
      >
        <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>

    <!-- Right: Feature Toggles -->
    <div class="flex items-center gap-1">
      <button
        @click="pdfStore.toggleAutoHighlight"
        :class="[
          'px-3 py-1.5 text-sm rounded-lg transition-colors',
          pdfStore.autoHighlight
            ? 'bg-primary-100 text-primary-700'
            : 'hover:bg-gray-100 text-gray-600'
        ]"
        title="自动高亮"
      >
        <span class="flex items-center gap-1.5">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
          高亮
        </span>
      </button>

      <button
        @click="pdfStore.toggleImageDescription"
        :class="[
          'px-3 py-1.5 text-sm rounded-lg transition-colors',
          pdfStore.imageDescription
            ? 'bg-primary-100 text-primary-700'
            : 'hover:bg-gray-100 text-gray-600'
        ]"
        title="图片说明"
      >
        <span class="flex items-center gap-1.5">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          图解
        </span>
      </button>

      <button
        @click="pdfStore.toggleAutoTranslate"
        :class="[
          'px-3 py-1.5 text-sm rounded-lg transition-colors',
          pdfStore.autoTranslate
            ? 'bg-primary-100 text-primary-700'
            : 'hover:bg-gray-100 text-gray-600'
        ]"
        title="自动翻译"
      >
        <span class="flex items-center gap-1.5">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
          </svg>
          翻译
        </span>
      </button>
    </div>
  </div>
</template>
