<script setup lang="ts">
// ------------------------- 导入依赖与组件 -------------------------
// 从 Vue 导入响应式 API（ref、watch），用于管理组件状态和监听变化
import { ref, watch } from 'vue'
// 引入 PDF store，用于管理 PDF 相关的状态和操作
import { usePdfStore } from '../../stores/pdf'
// 引入 RoadmapTab 组件，用于显示思维导图功能（确保 RoadmapTab.vue 文件存在于同级目录）
import RoadmapTab from '../roadmap/RoadmapTab.vue'

// 定义组件的 props，用于接收父组件传递的属性
const props = defineProps<{
  notesVisible?: boolean  // 笔记面板是否可见的可选属性
  chatVisible?: boolean   // 聊天面板是否可见的可选属性
}>()

// 定义组件的 emits，用于向父组件发出事件
const emit = defineEmits<{
  (e: 'toggle-notes-visibility'): void  // 切换笔记可见性的事件
  (e: 'toggle-chat-visibility'): void   // 切换聊天可见性的事件
}>()

// 获取 PDF store 的实例，用于访问和修改 PDF 相关状态
const pdfStore = usePdfStore()

// 定义页面输入框的响应式变量，用于跳转到指定页面
const pageInput = ref('')  // 存储用户输入的页面号

// 定义缩放输入框的响应式变量，初始值为当前缩放百分比的字符串形式
const scaleInput = ref(String(pdfStore.scalePercent))  // 存储用户输入的缩放百分比

// 控制 Roadmap（思维导图）显示状态的响应式变量
const showRoadmap = ref(false)  // 是否显示 Roadmap 面板

// 处理页面输入的函数，当用户输入页面号并按回车时调用
function handlePageInput() {
  const page = parseInt(pageInput.value)  // 将输入转换为整数
  if (!isNaN(page)) {  // 如果转换成功
    pdfStore.goToPage(page)  // 调用 store 方法跳转到指定页面
  }
  pageInput.value = ''  // 清空输入框
}

// 应用缩放输入的函数，当用户输入缩放值并按回车或失去焦点时调用
function applyScaleInput() {
  const value = parseFloat(scaleInput.value)  // 将输入转换为浮点数
  if (isNaN(value)) {  // 如果转换失败
    scaleInput.value = String(pdfStore.scalePercent)  // 重置为当前缩放百分比
    return  // 退出函数
  }
  // 计算新的缩放比例（假设基础缩放为 1.5），并设置到 store
  pdfStore.setScale((value / 100) * 1.5)
  scaleInput.value = String(pdfStore.scalePercent)  // 更新输入框值为新的百分比
}

// 监听 PDF store 中的缩放百分比变化，同步更新输入框
watch(
  () => pdfStore.scalePercent,  // 监听的响应式值
  (val) => {  // 当值变化时执行的回调
    scaleInput.value = String(val)  // 将新值转换为字符串并赋值给输入框
  }
)
</script>

<template>
  <div class="relative">
    <div class="flex items-center justify-between px-4 py-1.5 bg-white dark:bg-[#252526] border-b border-gray-200 dark:border-gray-800 shadow-sm">
      <!-- Left: Zoom Controls -->
      <div class="flex items-center gap-1.5">
        <button @click="pdfStore.zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title="缩小">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" /></svg>
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model="scaleInput"
            type="number"
            min="50" max="300" step="1"
            @keyup.enter="applyScaleInput" @blur="applyScaleInput"
            class="w-14 px-2 py-0.5 text-center text-sm border border-gray-300 dark:border-gray-600 dark:bg-[#3e3e42] dark:text-gray-200 rounded focus:outline-none focus:border-primary-500 dark:focus:border-primary-400 no-spinner"
          />
          <span class="text-sm text-gray-600 dark:text-gray-400">%</span>
        </div>
        <button @click="pdfStore.zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title="放大">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        </button>
      </div>

      <!-- Center: Page Navigation -->
      <div class="flex items-center gap-1.5">
        <button @click="pdfStore.prevPage" :disabled="pdfStore.currentPage <= 1" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed" title="上一页">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
        </button>
        <div class="flex items-center gap-1">
          <input
            v-model="pageInput"
            type="text"
            :placeholder="String(pdfStore.currentPage)"
            @keyup.enter="handlePageInput"
            class="w-10 px-2 py-0.5 text-center text-sm border border-gray-300 dark:border-gray-600 dark:bg-[#3e3e42] dark:text-gray-200 rounded focus:outline-none focus:border-primary-500 dark:focus:border-primary-400"
          />
          <span class="text-sm text-gray-500 dark:text-gray-400">/</span>
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ pdfStore.totalPages || '-' }}</span>
        </div>
        <button @click="pdfStore.nextPage" :disabled="pdfStore.currentPage >= pdfStore.totalPages" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed" title="下一页">
          <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        </button>
      </div>

      <!-- Right: Roadmap Button + Panel Toggles -->
      <div class="flex items-center gap-1">
        <button
          @click="showRoadmap = !showRoadmap"
          :class="[
            'px-2.5 py-1 text-sm rounded-lg transition-colors',
            showRoadmap
              ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          title="思维导图"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" /></svg>
            Roadmap
          </span>
        </button>

        <!-- 分割线 -->
        <div class="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1"></div>

        <!-- 笔记开关 -->
        <button
          @click="emit('toggle-notes-visibility')"
          :class="[
            'px-2 py-1 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.notesVisible
              ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          :title="props.notesVisible ? '隐藏笔记' : '显示笔记'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </button>

        <!-- 对话开关 -->
        <button
          @click="emit('toggle-chat-visibility')"
          :class="[
            'px-2 py-1 text-sm rounded-lg transition-colors flex items-center gap-1',
            props.chatVisible
              ? 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
              : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
          ]"
          :title="props.chatVisible ? '隐藏对话' : '显示对话'"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 2. 使用 Teleport 将窗口渲染到 body，确保可见且不被遮挡 -->
    <Teleport to="body">
      <RoadmapTab 
        v-if="showRoadmap" 
        @close="showRoadmap = false" 
      />
    </Teleport>
  </div>
</template>

<style>
.no-spinner::-webkit-outer-spin-button,
.no-spinner::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.no-spinner[type='number'] {
  -moz-appearance: textfield;
}
</style>
