<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API：ref 用于创建响应式变量，onUnmounted 用于组件卸载时的清理工作
import { ref, onUnmounted } from 'vue'
// 引入 AI store，用于管理 AI 相关的全局状态，如翻译结果
import { useAiStore } from '../../stores/ai'
// 引入 Library store，用于管理文献库相关的状态，如当前文档 ID
import { useLibraryStore } from '../../stores/library'
// 引入 AI API，用于调用后端的 AI 服务，如翻译文本
import { aiApi } from '../../api'
// 引入 PDF store 和 Highlight 类型，用于管理 PDF 高亮功能
import { usePdfStore, type Highlight } from '../../stores/pdf'

// 定义组件接收的 props：包括工具提示的位置、选中的文本、模式（选择或高亮）、高亮对象
const props = defineProps<{
  position: { x: number; y: number }
  text: string
  mode?: 'selection' | 'highlight'
  highlight?: Highlight | null
}>()

// 定义组件发出的自定义事件：关闭工具提示和引用文本
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'quote', text: string): void
}>()

// 初始化各个 store 实例，用于在组件中访问和修改全局状态
const aiStore = useAiStore()
const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

// --- 颜色选择器相关状态 ---
// 颜色选择器是否打开的标志
const isColorPickerOpen = ref(false)
// 当前选择的自定义颜色值
const customColor = ref('#000000')
// 是否已经设置了自定义颜色的标志
const isCustomColorSet = ref(false)

// --- 翻译弹窗相关状态 ---
// 是否显示翻译结果弹窗的标志
const showTranslation = ref(false)
// 是否正在进行翻译的标志
const isTranslating = ref(false)
// 翻译结果的文本内容
const translationResult = ref('')

// --- 拖拽相关状态 ---
// 拖拽状态对象，包含拖拽过程中的各种状态信息
const dragState = ref({
  isDragging: false, // 是否正在拖拽
  startX: 0, // 鼠标按下的初始 X 位置
  startY: 0, // 鼠标按下的初始 Y 位置
  offsetX: 0, // 盒子当前的 X 偏移量 (px)
  offsetY: 0, // 盒子当前的 Y 偏移量 (px)
  prevOffsetX: 0, // 记录上一次结束时的 X 偏移量
  prevOffsetY: 0 // 记录上一次结束时的 Y 偏移量
})

// 预定义的颜色选项数组，每个选项包含标签和颜色值
const colorOptions = [
  { label: '亮黄', value: '#F6E05E' },
  { label: '薄绿', value: '#9AE6B4' },
  { label: '天蓝', value: '#63B3ED' },
  { label: '柔粉', value: '#FBB6CE' },
  { label: '橘橙', value: '#F6AD55' }
]

// --- 拖拽处理函数 (已优化) ---
// 开始拖拽函数：处理鼠标按下事件，初始化拖拽状态
function startDrag(event: MouseEvent) {
  // 阻止默认事件，防止选中文本或其他默认行为
  event.preventDefault()
  // 设置拖拽状态为 true，表示开始拖拽
  dragState.value.isDragging = true
  // 记录鼠标按下时的起始位置
  dragState.value.startX = event.clientX
  dragState.value.startY = event.clientY
  // 记录开始拖动前盒子已经在的位置偏移量
  dragState.value.prevOffsetX = dragState.value.offsetX
  dragState.value.prevOffsetY = dragState.value.offsetY
  // 添加全局鼠标移动和鼠标松开事件监听器
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

// 拖拽中函数：处理鼠标移动事件，更新拖拽位置
function onDrag(event: MouseEvent) {
  // 如果没有在拖拽状态，直接返回
  if (!dragState.value.isDragging) return
  // 计算鼠标从起始位置移动的距离（纯像素值）
  const deltaX = event.clientX - dragState.value.startX
  const deltaY = event.clientY - dragState.value.startY
  // 更新盒子的偏移量 = 之前的偏移量 + 当前的移动距离
  dragState.value.offsetX = dragState.value.prevOffsetX + deltaX
  dragState.value.offsetY = dragState.value.prevOffsetY + deltaY
}

// 停止拖拽函数：处理鼠标松开事件，结束拖拽
function stopDrag() {
  // 设置拖拽状态为 false，表示停止拖拽
  dragState.value.isDragging = false
  // 移除全局鼠标事件监听器
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

// 组件卸载时的清理函数：移除可能遗留的事件监听器
onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
})

// 处理自定义颜色变化函数：当用户选择自定义颜色时调用
function handleCustomColorChange(event: Event) {
  // 将事件目标转换为 HTML 输入元素
  const input = event.target as HTMLInputElement
  // 获取输入的颜色值
  const color = input.value
  // 更新自定义颜色变量
  customColor.value = color
  // 设置已设置自定义颜色的标志
  isCustomColorSet.value = true
  // 调用颜色选择处理函数
  handleColorSelect(color)
}

// 处理翻译函数：异步函数，调用 AI API 进行文本翻译
async function handleTranslate() {
  // 显示翻译结果弹窗
  showTranslation.value = true
  // 设置正在翻译的标志
  isTranslating.value = true
  // 清空之前的翻译结果
  translationResult.value = ''
  // 每次点击翻译按钮，重置弹窗位置回到菜单正上方
  dragState.value.offsetX = 0
  dragState.value.offsetY = 0
  try {
    // 获取当前文档的 ID，用于上下文
    const pdfId = libraryStore.currentDocumentId
    // 调用 AI API 翻译选中的文本
    const response = await aiApi.translateText(props.text, pdfId || undefined)
    // 如果响应成功且有翻译文本，设置结果并更新 AI store
    if (response && response.translatedText) {
       translationResult.value = response.translatedText
       aiStore.setTranslation(response)
    } else {
       // 如果没有翻译结果，设置错误提示
       translationResult.value = "未能获取翻译结果"
    }
  } catch (error) {
    // 捕获翻译失败的错误并记录到控制台
    console.error('Translation failed:', error)
    // 设置错误提示信息
    translationResult.value = "翻译请求失败，请稍后重试。"
  } finally {
    // 无论成功还是失败，都停止翻译状态
    isTranslating.value = false
  }
}

// 关闭翻译函数：隐藏翻译弹窗并重置位置
function closeTranslation() {
  // 隐藏翻译弹窗
  showTranslation.value = false
  // 重置弹窗偏移位置
  dragState.value.offsetX = 0
  dragState.value.offsetY = 0
}

// 处理引用函数：发出引用事件，将选中文本作为引用
function handleQuote() {
  // 发出引用事件，传递选中的文本
  emit('quote', props.text)
  // 发出关闭事件，关闭工具提示
  emit('close')
}

// 处理高亮函数：根据当前模式添加或移除高亮
function handleHighlight() {
  // 如果是高亮模式且存在高亮对象，则移除该高亮
  if (props.mode === 'highlight' && props.highlight) {
    pdfStore.removeHighlight(props.highlight.id)
  } else {
    // 否则，从当前文本选择添加新的高亮
    pdfStore.addHighlightFromSelection()
  }
  // 关闭工具提示
  emit('close')
}

// 切换颜色选择器函数：打开或关闭颜色选择器面板
function toggleColorPicker(event: MouseEvent) {
  // 阻止事件冒泡，防止触发其他点击事件
  event.stopPropagation()
  // 如果要打开颜色选择器（之前是关闭状态）
  if (!isColorPickerOpen.value) {
    // 如果是高亮模式且有高亮对象，设置当前高亮的颜色为默认
    if (props.mode === 'highlight' && props.highlight) {
      customColor.value = props.highlight.color
      isCustomColorSet.value = true
    }
  }
  // 切换颜色选择器的打开状态
  isColorPickerOpen.value = !isColorPickerOpen.value
}

// 处理颜色选择函数：设置选中的颜色为高亮颜色
function handleColorSelect(color: string) {
  // 如果是高亮模式且有高亮对象，更新该高亮的颜色
  if (props.mode === 'highlight' && props.highlight) {
    pdfStore.updateHighlightColor(props.highlight.id, color)
  } else {
    // 否则，设置默认的高亮颜色（用于新高亮）
    pdfStore.setHighlightColor(color)
  }
  // 关闭颜色选择器
  isColorPickerOpen.value = false
}
</script>

<template>
  <div
    class="fixed z-50 transform -translate-x-1/2 -translate-y-full"
    :style="{
      left: `${position.x}px`,
      top: `${position.y}px`
    }"
  >
    <!-- 翻译结果悬浮框 -->
    <div 
      v-if="showTranslation" 
      class="absolute bottom-full left-1/2 mb-3 w-64 sm:w-80 bg-gray-800 text-white rounded-lg shadow-xl border border-gray-700 overflow-hidden flex flex-col transition-shadow will-change-transform"
      :class="{ 'shadow-2xl ring-1 ring-gray-600': dragState.isDragging }"
      :style="{ 
        transform: `translateX(-50%) translate(${dragState.offsetX}px, ${dragState.offsetY}px)` 
      }"
      @click.stop
    >
      <!-- 头部：标题和关闭按钮 -->
      <div 
        class="flex justify-between items-center px-3 py-2 bg-gray-900/50 border-b border-gray-700 select-none"
        :class="dragState.isDragging ? 'cursor-grabbing' : 'cursor-grab'"
        @mousedown="startDrag"
      >
        <span class="text-xs font-medium text-gray-300">AI 翻译</span>
        <button @click="closeTranslation" class="text-gray-400 hover:text-white cursor-pointer" @mousedown.stop>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
      
      <!-- 内容区域 -->
      <div class="p-3 text-sm leading-relaxed max-h-48 overflow-y-auto custom-scrollbar cursor-default" @mousedown.stop>
        <div v-if="isTranslating" class="flex items-center justify-center py-2 space-x-2 text-gray-400">
          <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>正在翻译...</span>
        </div>
        <div v-else>
          {{ translationResult }}
        </div>
      </div>
    </div>

    <!-- 主菜单 (保持不变) -->
    <div class="relative bg-gray-800 text-white rounded-lg shadow-xl py-1">
      <div class="flex items-center divide-x divide-gray-600">
        <!-- 翻译按钮 -->
        <button
          @click="handleTranslate"
          class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
          :class="{ 'text-blue-400': showTranslation }"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
          </svg>
          翻译
        </button>

        <!-- 高亮按钮 -->
        <button
          @click="handleHighlight"
          class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
        >
          <svg v-if="mode !== 'highlight'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span class="flex items-center">{{ mode === 'highlight' ? '取消高亮' : '高亮' }}</span>
        </button>

        <!-- 颜色选择器 -->
        <div class="relative">
          <button
            @click.stop="toggleColorPicker"
            class="px-2 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1 text-sm"
            :title="mode === 'highlight' ? '更改高亮颜色' : '选择高亮颜色'"
          >
            <span
              class="w-5 h-5 rounded-full border border-white/60 shadow-sm block"
              :style="{ backgroundColor: mode === 'highlight' && highlight ? highlight.color : pdfStore.highlightColor }"
            ></span>
          </button>

          <div
            v-if="isColorPickerOpen"
            class="absolute left-1/2 -translate-x-1/2 mt-2 bg-gray-900 rounded-lg shadow-xl px-3 py-2 flex gap-2"
            @click.stop
          >
            <button
              v-for="option in colorOptions"
              :key="option.value"
              @click="handleColorSelect(option.value)"
              class="w-6 h-6 rounded-full border border-white/70 shadow-sm focus:outline-none focus:ring-2 focus:ring-white/70"
              :style="{ backgroundColor: option.value }"
              :title="option.label"
            ></button>
            
            <div class="relative w-6 h-6 rounded-full border border-white/70 shadow-sm overflow-hidden group cursor-pointer" title="自定义颜色">
              <div 
                class="absolute inset-0 w-full h-full"
                :style="{ 
                  background: isCustomColorSet ? customColor : 'conic-gradient(from 180deg at 50% 50%, #FF0000 0deg, #FFFF00 60deg, #00FF00 120deg, #00FFFF 180deg, #0000FF 240deg, #FF00FF 300deg, #FF0000 360deg)'
                }"
              ></div>
              <input 
                type="color" 
                v-model="customColor"
                @change="handleCustomColorChange"
                class="absolute inset-0 w-full h-full opacity-0 cursor-pointer p-0 border-none"
              />
            </div>
          </div>
        </div>

        <!-- 引用按钮 -->
        <button
          @click="handleQuote"
          class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>
          引用
        </button>
      </div>

      <!-- Arrow -->
      <div class="absolute left-1/2 bottom-0 transform -translate-x-1/2 translate-y-full">
        <div class="border-8 border-transparent border-t-gray-800"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 隐藏滚动条但保留功能 */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}
.custom-scrollbar:hover::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.3);
}

/* 性能优化：提示浏览器该元素会变化 */
.will-change-transform {
  will-change: transform;
}
</style>
