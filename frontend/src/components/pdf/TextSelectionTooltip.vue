<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
import { ref } from 'vue'
import { usePdfStore, type Highlight } from '../../stores/pdf'
import { useTranslationStore } from '../../stores/translation'
import { useSelectText } from '../../composables/useSelectText'


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
const pdfStore = usePdfStore()
const translateStore = useTranslationStore()
const dragStore = useSelectText()

// --- 颜色选择器相关状态 ---
// 颜色选择器是否打开的标志
const isColorPickerOpen = ref(false)
// 当前选择的自定义颜色值
const customColor = ref('#000000')
// 是否已经设置了自定义颜色的标志
const isCustomColorSet = ref(false)

// 预定义的颜色选项数组，每个选项包含标签和颜色值
const colorOptions = [
  { label: '亮黄', value: '#F6E05E' },
  { label: '薄绿', value: '#9AE6B4' },
  { label: '天蓝', value: '#63B3ED' },
  { label: '柔粉', value: '#FBB6CE' },
  { label: '橘橙', value: '#F6AD55' }
]

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

// 处理翻译函数：调用 composable 并重置位置
async function handleTranslate() {
  dragStore.resetDrag() // 每次点击翻译按钮，重置弹窗位置回到菜单正上方
  
  // 1. 设置 Panel 的位置（让 Panel 出现在当前鼠标附近，稍微错开一点）
  translateStore.updateTextPanelPosition({
    x: props.position.x,
    y: props.position.y + 40
  })

  // 2. 触发文本翻译
  await translateStore.translateText(props.text)
  
  // 3. 关闭当前的 Tooltip 菜单
  emit('close')
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
    <!-- 主菜单 (保持不变) -->
    <div class="relative bg-gray-800 text-white rounded-lg shadow-xl py-1">
      <div class="flex items-center divide-x divide-gray-600">
        <!-- 翻译按钮 -->
        <button
          @click="handleTranslate"
          class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
          :class="{ 'text-blue-400': translateStore.showTextTranslation }"
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
