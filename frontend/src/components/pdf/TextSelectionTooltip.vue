<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useAiStore } from '../../stores/ai'
import { useLibraryStore } from '../../stores/library'
import { aiApi } from '../../api'
import { usePdfStore, type Highlight } from '../../stores/pdf'

const props = defineProps<{
  position: { x: number; y: number }
  text: string
  mode?: 'selection' | 'highlight'
  highlight?: Highlight | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'quote', text: string): void
}>()

const aiStore = useAiStore()
const pdfStore = usePdfStore()
const libraryStore = useLibraryStore()

// --- 颜色选择器相关状态 ---
const isColorPickerOpen = ref(false)
const customColor = ref('#000000')
const isCustomColorSet = ref(false)

// --- 翻译弹窗相关状态 ---
const showTranslation = ref(false)
const isTranslating = ref(false)
const translationResult = ref('')

// --- 拖拽相关状态 ---
const dragState = ref({
  isDragging: false,
  startX: 0, // 鼠标按下的初始 X
  startY: 0, // 鼠标按下的初始 Y
  offsetX: 0, // 盒子当前的 X 偏移量 (px)
  offsetY: 0, // 盒子当前的 Y 偏移量 (px)
  prevOffsetX: 0, // 记录上一次结束时的偏移量
  prevOffsetY: 0 
})

const colorOptions = [
  { label: '亮黄', value: '#F6E05E' },
  { label: '薄绿', value: '#9AE6B4' },
  { label: '天蓝', value: '#63B3ED' },
  { label: '柔粉', value: '#FBB6CE' },
  { label: '橘橙', value: '#F6AD55' }
]

// --- 拖拽处理函数 (已优化) ---
function startDrag(event: MouseEvent) {
  event.preventDefault() // 防止选中文本
  dragState.value.isDragging = true
  
  // 记录鼠标起始位置
  dragState.value.startX = event.clientX
  dragState.value.startY = event.clientY
  
  // 记录开始拖动前盒子已经在的位置
  dragState.value.prevOffsetX = dragState.value.offsetX
  dragState.value.prevOffsetY = dragState.value.offsetY
  
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!dragState.value.isDragging) return
  
  // 计算鼠标移动的距离 (纯像素值)
  const deltaX = event.clientX - dragState.value.startX
  const deltaY = event.clientY - dragState.value.startY
  
  // 更新盒子的偏移量 = 之前的偏移 + 现在的移动距离
  dragState.value.offsetX = dragState.value.prevOffsetX + deltaX
  dragState.value.offsetY = dragState.value.prevOffsetY + deltaY
}

function stopDrag() {
  dragState.value.isDragging = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
})

function handleCustomColorChange(event: Event) {
  const input = event.target as HTMLInputElement
  const color = input.value
  customColor.value = color
  isCustomColorSet.value = true
  handleColorSelect(color)
}

async function handleTranslate() {
  showTranslation.value = true
  isTranslating.value = true
  translationResult.value = '' 
  
  // 每次点击翻译按钮，重置位置回到菜单正上方
  dragState.value.offsetX = 0
  dragState.value.offsetY = 0

  try {
    const pdfId = libraryStore.currentDocumentId
    const response = await aiApi.translateText(props.text, pdfId || undefined)
    if (response && response.translatedText) {
       translationResult.value = response.translatedText
       aiStore.setTranslation(response)
    } else {
       translationResult.value = "未能获取翻译结果"
    }
  } catch (error) {
    console.error('Translation failed:', error)
    translationResult.value = "翻译请求失败，请稍后重试。"
  } finally {
    isTranslating.value = false
  }
}

function closeTranslation() {
  showTranslation.value = false
  dragState.value.offsetX = 0
  dragState.value.offsetY = 0
}

function handleQuote() {
  emit('quote', props.text) 
  emit('close')
}

function handleHighlight() {
  if (props.mode === 'highlight' && props.highlight) {
    pdfStore.removeHighlight(props.highlight.id)
  } else {
    pdfStore.addHighlightFromSelection()
  }
  emit('close')
}

function toggleColorPicker(event: MouseEvent) {
  event.stopPropagation()
  if (!isColorPickerOpen.value) {
    if (props.mode === 'highlight' && props.highlight) {
      customColor.value = props.highlight.color
      isCustomColorSet.value = true
    }
  }
  isColorPickerOpen.value = !isColorPickerOpen.value
}

function handleColorSelect(color: string) {
  if (props.mode === 'highlight' && props.highlight) {
    pdfStore.updateHighlightColor(props.highlight.id, color)
  } else {
    pdfStore.setHighlightColor(color)
  }
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
