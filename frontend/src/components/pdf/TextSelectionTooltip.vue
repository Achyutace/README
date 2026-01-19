<script setup lang="ts">
import { useAiStore } from '../../stores/ai'
import { aiApi } from '../../api'

const props = defineProps<{
  position: { x: number; y: number }
  text: string
}>()

const emit = defineEmits<{
  close: []
}>()

const aiStore = useAiStore()

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
  // TODO: Implement highlight functionality
  emit('close')
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
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
        高亮
      </button>

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
