<script setup lang="ts">
// ------------------------- 导入依赖与状态 -------------------------
// 引入 Vue 响应式 API：ref 用于创建响应式变量，computed 用于计算属性，watch 用于监听响应式数据的变化
import { ref, computed, watch } from 'vue'
// 引入 PDF store，用于管理 PDF 相关的全局状态
import { usePdfStore } from '../../stores/pdf'
import { clamp } from '@vueuse/core'

// 初始化 PDF store 实例，获取 store 的方法和状态
const pdfStore = usePdfStore()

// 卡片状态：定义响应式变量
// 是否展开摘要的标志
const isExpanded = ref(false)
// 是否正在拖拽卡片的标志
const isDragging = ref(false)
// 拖拽时的偏移量，用于计算拖拽位置
const dragOffset = ref({ x: 0, y: 0 })

// 从 store 获取数据：定义计算属性，从 store 中获取智能引用卡片的相关数据
// 卡片是否可见
const isVisible = computed(() => pdfStore.smartRefCard.isVisible)
// 是否正在加载论文信息
const isLoading = computed(() => pdfStore.smartRefCard.isLoading)
// 当前显示的论文数据
const paper = computed(() => pdfStore.smartRefCard.paper)
// 卡片在屏幕上的位置
const position = computed(() => pdfStore.smartRefCard.position)
// 错误信息，如果有的话
const error = computed(() => pdfStore.smartRefCard.error)

// 格式化作者列表：计算属性，用于格式化论文作者的显示
const formattedAuthors = computed(() => {
  // 如果论文数据中没有作者信息，返回空字符串
  if (!paper.value?.authors) return ''
  // 返回前5个作者的名字，用两个空格分隔
  return paper.value.authors.slice(0, 5).join('  ')
})

// 截断摘要：计算属性，根据展开状态决定是否截断摘要文本
const truncatedAbstract = computed(() => {
  // 如果没有摘要，返回空字符串
  if (!paper.value?.abstract) return ''
  // 获取摘要文本
  const abstract = paper.value.abstract
  // 如果摘要已展开或摘要长度小于等于200字符，返回完整摘要
  if (isExpanded.value || abstract.length <= 200) {
    return abstract
  }
  // 否则，截取前200字符并添加省略号
  return abstract.slice(0, 200) + '...'
})

// 来源信息：计算属性，组合论文的来源信息（如 arXiv、期刊、年份）
const sourceInfo = computed(() => {
  // 如果没有论文数据，返回空字符串
  if (!paper.value) return ''
  // 初始化来源信息数组
  const parts = []
  // 如果有 arXiv ID，添加 'arXiv'
  if (paper.value.arxivId) {
    parts.push('arXiv')
  }
  // 如果有会议或期刊名称，添加 venue
  if (paper.value.venue) {
    parts.push(paper.value.venue)
  }
  // 如果有年份，添加年份
  if (paper.value.year) {
    parts.push(paper.value.year)
  }
  // 用 ' · ' 连接所有部分并返回
  return parts.join(' · ')
})

// 拖动开始函数：处理鼠标按下事件，开始拖拽卡片
function startDrag(e: MouseEvent) {
  // 设置拖拽状态为 true
  isDragging.value = true
  // 计算初始偏移量：鼠标当前位置减去卡片的当前位置
  dragOffset.value = {
    x: e.clientX - position.value.x,
    y: e.clientY - position.value.y
  }
  // 添加全局鼠标移动和鼠标松开事件监听器
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  // 阻止默认的鼠标事件行为
  e.preventDefault()
}

// 拖动中函数：处理鼠标移动事件，更新卡片位置
function onDrag(e: MouseEvent) {
  // 如果没有在拖拽状态，返回
  if (!isDragging.value) return
  // 计算新的 X 和 Y 位置
  const newX = e.clientX - dragOffset.value.x
  const newY = e.clientY - dragOffset.value.y
  // 保持卡片在视口内：X 坐标限制在 0 到 窗口宽度-400 之间
  const clampedX = clamp(newX, 0, window.innerWidth - 400)
  
  // Y 坐标限制在 0 到 窗口高度-100 之间
  const clampedY = clamp(newY, 0, window.innerHeight - 100)
  // 更新 store 中的卡片位置
  pdfStore.updateSmartRefPosition({ x: clampedX, y: clampedY })
}

// 拖动结束函数：处理鼠标松开事件，停止拖拽
function stopDrag() {
  // 设置拖拽状态为 false
  isDragging.value = false
  // 移除全局事件监听器
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭卡片函数：关闭智能引用卡片
function closeCard() {
  // 调用 store 方法关闭卡片
  pdfStore.closeSmartRefCard()
  // 重置摘要展开状态
  isExpanded.value = false
}

// 打开论文链接函数：在新标签页中打开论文的 URL
function openPaperUrl() {
  // 如果论文有 URL，打开链接
  if (paper.value?.url) {
    window.open(paper.value.url, '_blank')
  }
}

// 添加到文献库函数：异步函数，将论文添加到文献库（目前为占位符）
async function addToLibrary() {
  // 如果没有论文数据，返回
  if (!paper.value) return
  // TODO: 实现添加到文献库的逻辑
  // 这里可以调用 libraryStore 的方法
  // 暂时显示开发中提示
  alert('添加到文献库功能开发中')
}

// 保存到笔记函数：将论文信息格式化为笔记并复制到剪贴板
function saveToNotes() {
  // 如果没有论文数据，返回
  if (!paper.value) return
  // 格式化为 Markdown 格式的笔记内容
  const noteContent = `## ${paper.value.title}\n\n**作者:** ${paper.value.authors?.join(', ')}\n\n**摘要:** ${paper.value.abstract || '无'}\n\n**来源:** ${sourceInfo.value}\n\n**链接:** ${paper.value.url || '无'}`
  // TODO: 调用笔记服务保存
  // 暂时复制到剪贴板
  navigator.clipboard.writeText(noteContent)
  // 显示提示信息
  alert('已复制到剪贴板')
}

// 复制 BibTeX 函数：生成 BibTeX 格式的引用并复制到剪贴板
function copyBibTeX() {
  // 如果没有论文数据，返回
  if (!paper.value) return
  // 构建 BibTeX 所需的字段
  const authors = paper.value.authors?.join(' and ') || 'Unknown'
  const year = paper.value.year || 'n.d.'
  const title = paper.value.title || 'Untitled'
  const venue = paper.value.venue || ''
  const doi = paper.value.doi || ''
  // 构建完整的 BibTeX 字符串
  const bibtex = `@article{${paper.value.paperId || 'ref'},
  author = {${authors}},
  title = {${title}},
  year = {${year}},
  ${venue ? `journal = {${venue}},` : ''}
  ${doi ? `doi = {${doi}},` : ''}
}`
  // 复制 BibTeX 到剪贴板
  navigator.clipboard.writeText(bibtex)
  // 显示提示信息
  alert('BibTeX 已复制到剪贴板')
}

// 组件卸载时清理：监听 isVisible 的变化，进行清理
watch(isVisible, (visible) => {
  // 如果卡片不可见，重置摘要展开状态
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
