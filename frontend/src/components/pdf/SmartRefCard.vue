<script setup lang="ts">
// ------------------------- 导入依赖与状态 -------------------------
// 引入 Vue 响应式 API 并初始化需要的 store
import { ref, computed, watch } from 'vue'
import { usePdfStore } from '../../stores/pdf'

const pdfStore = usePdfStore()

// 卡片状态
const isExpanded = ref(false)
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// 从 store 获取数据
const isVisible = computed(() => pdfStore.smartRefCard.isVisible)
const isLoading = computed(() => pdfStore.smartRefCard.isLoading)
const paper = computed(() => pdfStore.smartRefCard.paper)
const position = computed(() => pdfStore.smartRefCard.position)
const error = computed(() => pdfStore.smartRefCard.error)

// 格式化作者列表
const formattedAuthors = computed(() => {
  if (!paper.value?.authors) return ''
  return paper.value.authors.slice(0, 5).join('  ')
})

// 截断摘要
const truncatedAbstract = computed(() => {
  if (!paper.value?.abstract) return ''
  const abstract = paper.value.abstract
  if (isExpanded.value || abstract.length <= 200) {
    return abstract
  }
  return abstract.slice(0, 200) + '...'
})

// 来源信息
const sourceInfo = computed(() => {
  if (!paper.value) return ''
  const parts = []
  if (paper.value.arxivId) {
    parts.push('arXiv')
  }
  if (paper.value.venue) {
    parts.push(paper.value.venue)
  }
  if (paper.value.year) {
    parts.push(paper.value.year)
  }
  return parts.join(' · ')
})

// 拖动开始
function startDrag(e: MouseEvent) {
  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

// 拖动中
function onDrag(e: MouseEvent) {
  if (!isDragging.value) return
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  // 保持在视口内
  const clampedX = Math.max(0, Math.min(window.innerWidth - 400, newX))
  const clampedY = Math.max(0, Math.min(window.innerHeight - 100, newY))
  pdfStore.updateSmartRefPosition({ x: clampedX, y: clampedY })
}

// 拖动结束
function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭卡片
function closeCard() {
  pdfStore.closeSmartRefCard()
  isExpanded.value = false
}

// 打开论文链接
function openPaperUrl() {
  if (paper.value?.url) {
    window.open(paper.value.url, '_blank')
  }
}

// 添加到文献库
async function addToLibrary() {
  if (!paper.value) return

  // TODO: 实现添加到文献库的逻辑
  // 这里可以调用 libraryStore 的方法
  alert('添加到文献库功能开发中')
}

// 保存到笔记
function saveToNotes() {
  if (!paper.value) return

  // 格式化为笔记内容
  const noteContent = `## ${paper.value.title}\n\n**作者:** ${paper.value.authors?.join(', ')}\n\n**摘要:** ${paper.value.abstract || '无'}\n\n**来源:** ${sourceInfo.value}\n\n**链接:** ${paper.value.url || '无'}`

  // TODO: 调用笔记服务保存
  // 暂时复制到剪贴板
  navigator.clipboard.writeText(noteContent)
  alert('已复制到剪贴板')
}

// 复制 BibTeX
function copyBibTeX() {
  if (!paper.value) return

  const authors = paper.value.authors?.join(' and ') || 'Unknown'
  const year = paper.value.year || 'n.d.'
  const title = paper.value.title || 'Untitled'
  const venue = paper.value.venue || ''
  const doi = paper.value.doi || ''

  const bibtex = `@article{${paper.value.paperId || 'ref'},
  author = {${authors}},
  title = {${title}},
  year = {${year}},
  ${venue ? `journal = {${venue}},` : ''}
  ${doi ? `doi = {${doi}},` : ''}
}`

  navigator.clipboard.writeText(bibtex)
  alert('BibTeX 已复制到剪贴板')
}

// 组件卸载时清理
watch(isVisible, (visible) => {
  if (!visible) {
    isExpanded.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="smart-ref-card fixed z-[9999] w-[380px] bg-white dark:bg-[#1e1e1e] rounded-xl shadow-2xl border border-blue-200 dark:border-blue-800 overflow-hidden"
      :style="{ left: position.x + 'px', top: position.y + 'px' }"
    >
      <!-- 拖动头部 -->
      <div
        class="flex items-center justify-between px-4 py-2 bg-blue-50 dark:bg-blue-900/30 cursor-move select-none border-b border-blue-100 dark:border-blue-800"
        @mousedown="startDrag"
      >
        <span class="text-xs font-medium text-blue-600 dark:text-blue-400">智能引用</span>
        <button
          @click="closeCard"
          class="p-1 hover:bg-blue-100 dark:hover:bg-blue-800 rounded-full transition-colors"
        >
          <svg class="w-4 h-4 text-blue-500 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- 内容区域 -->
      <div class="p-4 max-h-[400px] overflow-y-auto">
        <!-- 加载中 -->
        <div v-if="isLoading" class="flex flex-col items-center justify-center py-8">
          <div class="loading-spinner mb-3"></div>
          <span class="text-sm text-gray-500 dark:text-gray-400">正在获取论文信息...</span>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="text-center py-6">
          <svg class="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="text-sm text-gray-500 dark:text-gray-400">{{ error }}</p>
        </div>

        <!-- 论文信息 -->
        <div v-else-if="paper" class="space-y-3">
          <!-- 标题 -->
          <h3
            class="text-base font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 cursor-pointer leading-snug"
            @click="openPaperUrl"
          >
            {{ paper.title }}
            <svg v-if="paper.url" class="inline-block w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </h3>

          <!-- 作者 -->
          <p class="text-sm text-blue-500 dark:text-blue-400">
            {{ formattedAuthors }}
            <span v-if="paper.authors && paper.authors.length > 5" class="text-gray-400">
              等 {{ paper.authors.length }} 人
            </span>
          </p>

          <!-- 来源信息 -->
          <p v-if="sourceInfo" class="text-xs text-gray-500 dark:text-gray-400">
            {{ sourceInfo }}
            <span v-if="paper.citationCount" class="ml-2">
              · 被引用 {{ paper.citationCount }} 次
            </span>
          </p>

          <!-- 摘要 -->
          <div v-if="paper.abstract" class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            <p>{{ truncatedAbstract }}</p>
            <button
              v-if="paper.abstract.length > 200"
              @click="isExpanded = !isExpanded"
              class="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 text-xs mt-1"
            >
              {{ isExpanded ? '收起' : '查看更多' }}
            </button>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-2 pt-2 border-t border-gray-100 dark:border-gray-700">
            <button
              @click="saveToNotes"
              class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-800/50 rounded-full transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              保存
            </button>
            <button
              @click="addToLibrary"
              class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-800/50 rounded-full transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              添加到文献库
            </button>
          </div>

          <!-- 底部信息 -->
          <div class="flex items-center justify-between pt-2 text-xs text-gray-400 dark:text-gray-500">
            <span class="text-[10px]">*信息可能会更新或有误</span>
            <button
              @click="copyBibTeX"
              class="flex items-center gap-1 hover:text-blue-500 dark:hover:text-blue-400 transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              BibTeX
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.smart-ref-card {
  animation: slideIn 0.2s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
