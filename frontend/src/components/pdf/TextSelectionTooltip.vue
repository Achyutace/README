<script setup lang="ts">
import { ref } from 'vue'
import { useAiStore } from '../../stores/ai'
import { aiApi } from '../../api'
import { usePdfStore, type Highlight } from '../../stores/pdf'

const props = defineProps<{
  position: { x: number; y: number }
  text: string
  mode?: 'selection' | 'highlight'
  highlight?: Highlight | null
}>()

const emit = defineEmits<{
  close: []
}>()

const aiStore = useAiStore()
const pdfStore = usePdfStore()
const isColorPickerOpen = ref(false)
const customColor = ref('#000000')
const isCustomColorSet = ref(false)

const colorOptions = [
  { label: '亮黄', value: '#F6E05E' },
  { label: '薄绿', value: '#9AE6B4' },
  { label: '天蓝', value: '#63B3ED' },
  { label: '柔粉', value: '#FBB6CE' },
  { label: '橘橙', value: '#F6AD55' }
]

function handleCustomColorChange(event: Event) {
  const input = event.target as HTMLInputElement
  const color = input.value
  customColor.value = color
  isCustomColorSet.value = true
  handleColorSelect(color)
}

async function handleTranslate() {
  aiStore.isLoadingTranslation = true
  aiStore.setActiveTab('translation')

  try {
    const translation = await aiApi.translateText(props.text)
    aiStore.setTranslation(translation)
  } catch (error) {
    console.error('Translation failed:', error)
    // For demo, show mock translation
    aiStore.setTranslation({
      originalText: props.text,
      translatedText: `[翻译] ${props.text}`,
      sentences: [{ index: 1, original: props.text, translated: `[翻译] ${props.text}` }]
    })
  } finally {
    aiStore.isLoadingTranslation = false
    emit('close')
  }
}

function handleExplain() {
  aiStore.setActiveTab('chat')
  aiStore.addChatMessage({
    role: 'user',
    content: `请解释以下内容：\n\n"${props.text}"`
  })
  emit('close')
}

function handleCopy() {
  navigator.clipboard.writeText(props.text)
  emit('close')
}

function handleHighlight() {
  if (props.mode === 'highlight' && props.highlight) {
    // 取消高亮
    pdfStore.removeHighlight(props.highlight.id)
  } else {
    // 添加高亮
    pdfStore.addHighlightFromSelection()
  }
  emit('close')
}

function toggleColorPicker(event: MouseEvent) {
  event.stopPropagation()
  if (!isColorPickerOpen.value) {
    // 当打开颜色选择器时，如果是编辑已有高亮，将自定义颜色初始化为当前高亮颜色
    if (props.mode === 'highlight' && props.highlight) {
      customColor.value = props.highlight.color
      isCustomColorSet.value = true
    }
  }
  isColorPickerOpen.value = !isColorPickerOpen.value
}

function handleColorSelect(color: string) {
  if (props.mode === 'highlight' && props.highlight) {
    // 更新已有高亮的颜色
    pdfStore.updateHighlightColor(props.highlight.id, color)
  } else {
    // 设置新高亮的默认颜色
    pdfStore.setHighlightColor(color)
  }
  isColorPickerOpen.value = false
}
</script>

<template>
  <div
    class="fixed z-50 bg-gray-800 text-white rounded-lg shadow-xl py-1 transform -translate-x-1/2 -translate-y-full"
    :style="{
      left: `${position.x}px`,
      top: `${position.y}px`
    }"
  >
    <div class="flex items-center divide-x divide-gray-600">
      <button
        @click="handleTranslate"
        class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
        </svg>
        翻译
      </button>

      <button
        @click="handleExplain"
        class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        解释
      </button>

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

      <button
        @click="handleCopy"
        class="px-3 py-2 hover:bg-gray-700 transition-colors flex items-center gap-1.5 text-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
        </svg>
        复制
      </button>
    </div>

    <!-- Arrow -->
    <div class="absolute left-1/2 bottom-0 transform -translate-x-1/2 translate-y-full">
      <div class="border-8 border-transparent border-t-gray-800"></div>
    </div>
  </div>
</template>
