<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import type { CustomModel } from '../../types'

const props = defineProps<{
  isLoadingContent: boolean
  chatMode: 'agent' | 'simple'
  customModels: CustomModel[]
  selectedModel: string
  selectedText?: string
}>()

const emit = defineEmits<{
  (e: 'send', payload: { text: string; mode: 'agent' | 'simple'; model: string }): void
  (e: 'change-model', model: string): void
  (e: 'clear-selection'): void
  (e: 'open-model-modal'): void
  (e: 'delete-model', id: string): void
  (e: 'toggle-mode'): void
}>()

const inputMessage = ref('')
const inputAreaRef = ref<HTMLElement | null>(null)

// --- Menu States ---
const showPromptMenu = ref(false)
const showModelMenu = ref(false)
const showAtMenu = ref(false)
const showKeywordSubmenu = ref(false)
const isEditingPrompts = ref(false)

// --- File Attachment State ---
const fileInput = ref<HTMLInputElement | null>(null)
const attachedFiles = ref<{ name: string; id: string }[]>([])

// --- Reference State ---
const selectedReferences = ref<{ type: string; label: string; id: string }[]>([])

// --- Mock Keyword Indexes ---
const keywordIndexes = [
  { id: 'kw1', label: 'Chain-of-Thought' },
  { id: 'kw2', label: 'Unlearning' },
  { id: 'kw3', label: 'Fast-slow-VLA' },
]

// --- Prompt State ---
const defaultPrompts = [
  '这篇文章针对的问题的是什么？',
  '这篇论文有什么创新点？',
  '这篇论文有什么局限性或不足？',
  '这篇论文主要的研究方法是什么？',
  '这篇文章启发了哪些后续的研究？',
]
const userPrompts = ref<{ id: string; text: string }[]>(
  defaultPrompts.map((p, i) => ({ id: `sys_${i}`, text: p }))
)

// --- Methods ---

const sendMessage = (message?: string) => {
  const content = message || inputMessage.value.trim()
  if (!content || props.isLoadingContent) return
  emit('send', { text: content, mode: props.chatMode, model: props.selectedModel })
  if (!message) inputMessage.value = ''
  closeMenus()
}

const closeOtherMenus = (active: 'at' | 'model' | 'prompt') => {
  if (active !== 'at') { showAtMenu.value = false; showKeywordSubmenu.value = false }
  if (active !== 'model') showModelMenu.value = false
  if (active !== 'prompt') { showPromptMenu.value = false; isEditingPrompts.value = false }
}

const closeMenus = () => {
  showAtMenu.value = false
  showKeywordSubmenu.value = false
  showModelMenu.value = false
  showPromptMenu.value = false
  isEditingPrompts.value = false
}

// @ Menu
const toggleAtMenu = () => {
  showAtMenu.value = !showAtMenu.value
  if (!showAtMenu.value) showKeywordSubmenu.value = false
  closeOtherMenus('at')
}
const handleKeywordClick = () => {
  showKeywordSubmenu.value = !showKeywordSubmenu.value
}
const selectFrameMode = () => {
  console.log('Frame selection mode activated')
  closeMenus()
}
const selectKeywordIndex = (kw: { id: string; label: string }) => {
  if (!selectedReferences.value.find(r => r.id === kw.id)) {
    selectedReferences.value.push({ type: 'keyword', label: kw.label, id: kw.id })
  }
  closeMenus()
}
const removeReference = (id: string) => {
  selectedReferences.value = selectedReferences.value.filter(r => r.id !== id)
}

// File Attachment
const triggerFileInput = () => {
  fileInput.value?.click()
}
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files) {
    for (const file of target.files) {
      attachedFiles.value.push({ name: file.name, id: Date.now().toString() + file.name })
    }
  }
  target.value = ''
}
const removeFile = (id: string) => {
  attachedFiles.value = attachedFiles.value.filter(f => f.id !== id)
}

// Prompt Menu
const togglePromptMenu = () => {
  showPromptMenu.value = !showPromptMenu.value
  if (showPromptMenu.value) isEditingPrompts.value = false
  closeOtherMenus('prompt')
}
const handlePromptClick = (promptText: string) => {
  sendMessage(promptText)
  showPromptMenu.value = false
}
const toggleEditPrompts = () => {
  isEditingPrompts.value = !isEditingPrompts.value
}
const addNewPrompt = () => {
  userPrompts.value.push({ id: `new_${Date.now()}`, text: '' })
}
const removePrompt = (index: number) => {
  userPrompts.value.splice(index, 1)
}
const savePrompts = () => {
  userPrompts.value = userPrompts.value.filter(p => p.text.trim() !== '')
  isEditingPrompts.value = false
}

// Model Menu
const toggleModelMenu = () => {
  showModelMenu.value = !showModelMenu.value
  closeOtherMenus('model')
}
const selectModel = (modelName: string) => {
  emit('change-model', modelName)
  showModelMenu.value = false
}
const deleteCustomModel = (id: string, event: Event) => {
  event.stopPropagation()
  if (confirm('确定删除该自定义模型？')) {
    emit('delete-model', id)
  }
}

// Global click to close menus
const handleGlobalClick = (e: MouseEvent) => {
  if (inputAreaRef.value && !inputAreaRef.value.contains(e.target as Node)) {
    closeMenus()
  }
}
onMounted(() => document.addEventListener('click', handleGlobalClick))
onBeforeUnmount(() => document.removeEventListener('click', handleGlobalClick))
</script>

<template>
  <div ref="inputAreaRef" class="p-4 border-t border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-[#252526]/50 backdrop-blur-sm">
    
    <!-- Preview blocks (Selections + References + Files) -->
    <div v-if="selectedText || selectedReferences.length > 0 || attachedFiles.length > 0" class="flex flex-wrap gap-1.5 mb-2">
      
      <!-- PDF Selection Preview -->
      <div v-if="selectedText" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-xs">
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" /></svg>
        <span class="max-w-20 truncate" :title="selectedText">{{ selectedText }}</span>
        <button @click="$emit('clear-selection')" class="hover:text-gray-900 dark:hover:text-white">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>

      <!-- Reference Tags -->
      <div v-for="ref in selectedReferences" :key="ref.id" class="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs">
        <span class="text-primary-500">@</span>
        <span class="max-w-20 truncate">{{ ref.label }}</span>
        <button @click="removeReference(ref.id)" class="hover:text-primary-900">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>

      <!-- File Tags -->
      <div v-for="file in attachedFiles" :key="file.id" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
        <span class="max-w-20 truncate">{{ file.name }}</span>
        <button @click="removeFile(file.id)" class="hover:text-gray-900">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
    </div>

    <!-- Toolbar row -->
    <div class="flex items-center gap-1 mb-2">

      <!-- Prompts Menu -->
      <div class="relative">
        <button
          @click="togglePromptMenu"
          class="flex items-center gap-0.5 p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 transition-colors"
          :class="{ 'bg-gray-100 dark:bg-gray-700': showPromptMenu }"
          title="预设提示词"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </button>

        <!-- Prompt Dropdown -->
        <div v-if="showPromptMenu" class="absolute bottom-full left-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-2 min-w-64 max-w-sm z-50 shadow-lg">
          <div class="flex items-center justify-between px-3 pb-2 border-b border-gray-100 dark:border-gray-700 mb-1">
            <span class="text-xs font-semibold text-gray-500">提示词</span>
            <div class="flex gap-1">
              <button v-if="isEditingPrompts" @click="addNewPrompt" class="p-1 text-primary-700 hover:bg-primary-50 rounded transition-colors" title="新增提示词">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
              </button>
              <button @click="isEditingPrompts ? savePrompts() : toggleEditPrompts()" class="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors" :title="isEditingPrompts ? '保存' : '编辑'">
                <svg v-if="isEditingPrompts" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
              </button>
            </div>
          </div>
          <div class="max-h-60 overflow-y-auto">
            <div v-if="isEditingPrompts" class="px-2 space-y-1">
              <div v-for="(prompt, index) in userPrompts" :key="prompt.id" class="flex items-center gap-1">
                <input v-model="prompt.text" type="text" class="flex-1 text-xs border border-gray-200 dark:border-gray-600 dark:bg-[#3e3e42] dark:text-white rounded px-2 py-1.5 focus:border-primary-500 outline-none" placeholder="输入提示词..." />
                <button @click="removePrompt(index)" class="p-1 text-gray-400 hover:text-red-500">
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
            </div>
            <div v-else>
              <button
                v-for="prompt in userPrompts"
                :key="prompt.id"
                @click="handlePromptClick(prompt.text)"
                class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-[#3e3e42] truncate"
                :title="prompt.text"
              >
                {{ prompt.text }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- @ Button -->
      <div class="relative">
        <button
          @click="toggleAtMenu"
          class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors text-sm font-medium"
          :class="{ 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200': showAtMenu }"
          title="插入引用"
        >@</button>
        <div v-if="showAtMenu" class="absolute bottom-full left-0 mb-1 bg-gray-800/90 rounded-lg py-1 min-w-36 z-50">
          <div class="relative">
            <button @click="handleKeywordClick" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center justify-between">
              <span>本文关键词</span>
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            </button>
            <div v-if="showKeywordSubmenu" class="absolute left-full top-0 ml-1 bg-gray-800/90 rounded-lg py-1 min-w-32">
              <button @click="selectFrameMode" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50">框选模式</button>
              <div class="border-t border-gray-600 my-1"></div>
              <div class="px-2 py-1 text-xs text-gray-400">已建立索引</div>
              <button v-for="kw in keywordIndexes" :key="kw.id" @click="selectKeywordIndex(kw)" class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-gray-700/50">{{ kw.label }}</button>
            </div>
          </div>
          <button class="w-full text-left px-3 py-2 text-sm text-gray-400 cursor-not-allowed">已读论文</button>
        </div>
      </div>

      <!-- Attachment Button -->
      <button @click="triggerFileInput" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors" title="添加文件">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
      </button>
      <input ref="fileInput" type="file" multiple class="hidden" @change="handleFileSelect" />

      <!-- Chat Mode Toggle Button -->
      <button
        @click="$emit('toggle-mode')"
        class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
        :title="chatMode === 'agent' ? '当前: Agent 模式 (点击切换到简单聊天)' : '当前: 简单聊天模式 (点击切换到 Agent)'"
      >
        <!-- Agent mode icon: magnifier -->
        <svg v-if="chatMode === 'agent'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <!-- Simple mode icon: chat bubble -->
        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      </button>

      <!-- Model Selector -->
      <div class="relative ml-auto">
        <button
          @click="toggleModelMenu"
          class="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors text-xs"
          :class="{ 'bg-gray-100 dark:bg-gray-700': showModelMenu }"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
          <span class="max-w-24 truncate">{{ selectedModel }}</span>
          <svg class="w-3 h-3 transition-transform" :class="{ 'rotate-180': showModelMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </button>

        <div v-if="showModelMenu" class="absolute bottom-full right-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-1 min-w-36 max-w-48 z-50 shadow-lg">
          <button
            @click="selectModel('README Fusion')"
            class="w-full text-left px-2.5 py-2 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600/50 transition-colors"
            :class="{ 'bg-gray-100 dark:bg-gray-600/50': selectedModel === 'README Fusion' }"
          >README Fusion</button>

          <template v-if="customModels.length > 0">
            <div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
            <div v-for="model in customModels" :key="model.id" class="relative group">
              <button
                @click="selectModel(model.name)"
                class="w-full text-left px-2.5 py-2 pr-7 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600/50 transition-colors truncate"
                :class="{ 'bg-gray-100 dark:bg-gray-600/50': selectedModel === model.name }"
              >{{ model.name }}</button>
              <button
                @click="deleteCustomModel(model.id, $event)"
                class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-all"
              >
                <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </template>

          <div class="border-t border-gray-200 dark:border-gray-600 my-1"></div>
          <button
            @click="$emit('open-model-modal'); showModelMenu = false"
            class="w-full text-left px-2.5 py-2 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600/50 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >+ 添加自定义模型</button>
        </div>
      </div>
    </div>

    <!-- Textarea + Send Button -->
    <div class="flex gap-2 items-end">
      <div class="flex-1 relative">
        <textarea
          v-model="inputMessage"
          placeholder="输入问题..."
          @keydown.enter.exact.prevent="sendMessage()"
          class="w-full px-4 py-3 min-h-[46px] max-h-32 border border-gray-200 dark:border-gray-700 rounded-2xl focus:outline-none focus:border-gray-300 dark:focus:border-gray-600 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-800 text-sm bg-white dark:bg-[#3e3e42] dark:text-gray-200 transition-all duration-200 placeholder:text-gray-400 resize-none overflow-hidden"
          style="field-sizing: content;"
        ></textarea>
      </div>

      <button
        @click="sendMessage()"
        :disabled="!inputMessage.trim() || isLoadingContent"
        class="mb-1 p-2.5 rounded-xl transition-all duration-200 flex-shrink-0"
        :class="[
          inputMessage.trim()
            ? 'bg-gray-900 dark:bg-[#0e639c] text-white hover:bg-gray-800 dark:hover:bg-[#1177bb]'
            : 'bg-gray-100 dark:bg-[#2d2d30] text-gray-400 dark:text-gray-500 cursor-not-allowed'
        ]"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  </div>
</template>
