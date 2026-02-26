<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useMarkdownRenderer } from '../../composables/useMarkdownRenderer'
import type { ChatMessage, Citation } from '../../types'

const props = defineProps<{
  messages: ChatMessage[]
  isLoadingContent: boolean
  selectionMode?: boolean
  selectedIds?: Set<string>
}>()

const emit = defineEmits<{
  (e: 'click-citation', citations: Citation[], event: MouseEvent): void
  (e: 'resend', index: number): void
  (e: 'resend-edited', index: number, content: string): void
  (e: 'toggle-selection', id: string): void
}>()

const { tooltipState, renderMarkdown, handleMessageMouseOver, handleMessageMouseOut, handleMessageClick, handleTooltipEnter, handleTooltipLeave } = useMarkdownRenderer()

const messagesContainer = ref<HTMLElement | null>(null)
const editingIndex = ref<number | null>(null)
const editValue = ref('')

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 自动滚动
watch(() => props.messages.length, () => {
  nextTick(scrollToBottom)
})

const onCitationClick = (event: MouseEvent, citations: Citation[]) => {
  handleMessageClick(event, citations)
  emit('click-citation', citations, event)
}

const startEdit = (index: number, content: string) => {
  editingIndex.value = index
  editValue.value = content
}

const cancelEdit = () => {
  editingIndex.value = null
  editValue.value = ''
}

const submitEdit = (index: number) => {
  if (editValue.value.trim()) {
    emit('resend-edited', index, editValue.value.trim())
    editingIndex.value = null
  }
}

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text)
}

const vFocus = {
  mounted: (el: HTMLElement) => el.focus()
}

defineExpose({
  scrollToBottom
})
</script>

<template>
  <div class="h-full flex flex-col relative w-full overflow-hidden">
    <!-- Tooltip Component (Global Absolute Position within List) -->
    <div 
      v-if="tooltipState.visible && tooltipState.content"
      class="fixed z-[100] w-80 bg-white/98 dark:bg-[#1e1e1e]/98 backdrop-blur-md rounded-lg border border-blue-100/80 dark:border-gray-800 p-3 transition-opacity duration-200 shadow-xl overflow-hidden"
      :style="{ left: Math.min(tooltipState.x - 20, 1024) + 'px', top: (tooltipState.y - 8) + 'px', transform: 'translateY(-100%)' }"
      @mouseenter="handleTooltipEnter"
      @mouseleave="handleTooltipLeave"
    >
      <!-- Header: Type -->
      <div class="flex items-center justify-between mb-2">
        <span class="text-[9px] font-bold text-primary-400 dark:text-gray-400 uppercase tracking-widest">
          {{ tooltipState.content.source_type === 'vector' ? '知识库' : '关系网络' }}
        </span>
        <span v-if="tooltipState.content.score" class="text-[9px] text-primary-400/80 dark:text-gray-400">
          相似度 {{ (tooltipState.content.score * 100).toFixed(0) }}%
        </span>
      </div>

      <!-- Name -->
      <h4 class="font-bold text-xs text-slate-900 dark:text-gray-100 mb-1.5 leading-tight">
        {{ tooltipState.content.name || '检索内容' }}
      </h4>

      <!-- Text -->
      <p class="text-[11px] text-slate-600 dark:text-gray-400 leading-normal bg-blue-50/30 dark:bg-white/5 p-2 rounded border border-blue-50 dark:border-gray-800/50 line-clamp-6">
        {{ tooltipState.content.text }}
      </p>

      <!-- Footer -->
      <div v-if="tooltipState.content.url || tooltipState.content.page" class="flex justify-end mt-2 text-[9px]">
        <div v-if="tooltipState.content.url" class="text-primary-600 hover:underline cursor-pointer font-medium">查看详情</div>
        <span v-else class="text-slate-400">第 {{ tooltipState.content.page }} 页</span>
      </div>
    </div>



    <!-- Messages Area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto w-full px-4 pt-4 pb-2 space-y-4">
      <template v-if="messages.length > 0">
        <div 
          v-for="(message, index) in messages" 
          :key="message.id" 
          class="relative group w-full"
        >
          <!-- Branch Indicator -->
          <div v-if="message.meta?.resendFromIndex !== undefined" class="flex items-center gap-2 mb-4">
            <div class="h-[1px] flex-1 bg-blue-50 dark:bg-gray-800"></div>
            <span class="text-[10px] font-medium text-slate-400 uppercase tracking-widest px-2 py-0.5 rounded-full border border-blue-50 dark:border-gray-800 bg-blue-50/30 dark:bg-gray-900/50">
              分支对话
            </span>
            <div class="h-[1px] flex-1 bg-blue-50 dark:bg-gray-800"></div>
          </div>

          <!-- Message Container -->
          <div class="flex gap-4">
            <!-- Selection Checkbox -->
            <div v-if="selectionMode" class="flex-shrink-0 pt-2">
              <input 
                type="checkbox" 
                :checked="selectedIds?.has(message.id)"
                @change="emit('toggle-selection', message.id)"
                class="w-3.5 h-3.5 rounded border-blue-200 dark:border-slate-700 text-primary-600 dark:text-slate-100 focus:ring-0 focus:ring-offset-0 cursor-pointer transition-colors"
                title="选择消息"
              >
            </div>

            <!-- Message Body -->
            <div class="flex-1 min-w-0 relative">
              <!-- Content Render -->
              <div 
                :class="[
                  'w-full transition-all duration-200',
                  message.role === 'user' 
                    ? 'px-3.5 py-1.5 rounded-lg bg-blue-50/40 dark:bg-slate-900/30 border border-blue-100/50 dark:border-slate-700 user-message-pattern' 
                    : 'px-2 py-1.5 assistant-message-light'
                ]"
              >
                <!-- Edit Mode -->
                <div v-if="editingIndex === index" class="animate-in fade-in zoom-in-95 duration-200">
                  <textarea 
                    v-model="editValue"
                    class="w-full bg-transparent border-none focus:outline-none focus:ring-0 text-sm md:text-[15px] leading-snug text-gray-800 dark:text-gray-200 resize-none p-0 overflow-hidden"
                    placeholder="编辑消息..."
                    style="field-sizing: content;"
                    v-focus
                  ></textarea>
                  <div class="flex justify-end gap-2 mt-4 pt-3 border-t border-gray-100 dark:border-gray-800/50">
                    <button @click="cancelEdit" class="px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors">取消</button>
                    <button @click="submitEdit(index)" class="px-3 py-1.5 text-xs bg-primary-600 text-white hover:bg-primary-700 rounded-md transition-colors">确认重发</button>
                  </div>
                </div>

                <template v-else>
                  <!-- User Message Content -->
                  <p v-if="message.role === 'user'" class="text-sm md:text-[15px] whitespace-pre-wrap break-words leading-snug text-slate-800 dark:text-slate-200">
                    {{ message.content }}
                  </p>
                  
                  <!-- Assistant Message Content -->
                  <div v-else class="space-y-1.5">
                    <div 
                      class="markdown-body prose prose-sm md:prose-base max-w-none dark:prose-invert 
                             prose-p:leading-snug prose-pre:bg-[#282c34] prose-pre:m-0
                             prose-headings:font-semibold prose-headings:text-gray-800 dark:prose-headings:text-gray-100
                             prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                             text-gray-800 dark:text-gray-200"
                      v-html="renderMarkdown(message.content)"
                      @mouseover="handleMessageMouseOver($event, message.citations || [])"
                      @mouseout="handleMessageMouseOut"
                      @click="onCitationClick($event, message.citations || [])"
                    ></div>

                    <!-- AI Citations: Now inside the message body area -->
                    <div v-if="message.citations?.length" class="flex items-center gap-x-2 gap-y-1 flex-wrap pt-0.5 pb-0.5 text-[11px]">
                      <span 
                        v-for="(cite, citeIdx) in message.citations" 
                        :key="cite.id || citeIdx"
                        class="citation-ref text-slate-400 dark:text-slate-500 font-medium cursor-pointer hover:text-primary-600 dark:hover:text-primary-400 transition-colors duration-200 whitespace-nowrap"
                        :data-id="citeIdx + 1"
                        @mouseover="handleMessageMouseOver($event, message.citations || [])"
                        @mouseout="handleMessageMouseOut"
                        @click="onCitationClick($event, message.citations || [])"
                      >
                        <span class="opacity-60">[{{ citeIdx + 1 }}]</span>
                        <span class="max-w-[120px] truncate inline-block align-bottom ml-0.5">{{ cite.name || '检索片段' }}</span>
                      </span>
                    </div>
                  </div>
                </template>
              </div>

              <!-- AI Footer: Single line divider with Timestamp and Copy Button below it -->
              <div v-if="message.role === 'assistant'" class="mt-1">
                <!-- Top: Single unified line -->
                <div class="h-[1px] w-full bg-blue-100/30 dark:bg-slate-800/50 mb-1"></div>
                
                <!-- Bottom: Timestamp (Left) and Copy Button (Right) -->
                <div class="flex items-center justify-between px-1">
                  <span class="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                    {{ new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
                  </span>

                  <button 
                    @click="copyToClipboard(message.content)"
                    class="p-0.5 text-slate-500 dark:text-slate-400 hover:text-primary-600 transition-colors"
                    title="复制内容"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" /></svg>
                  </button>
                </div>
              </div>

              <!-- User Footer -->
              <div v-else class="mt-1 flex items-center justify-between px-1">
                <div class="flex items-center gap-2">
                  <span class="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                    {{ new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}
                  </span>
                  <span v-if="message.meta?.edited" class="text-[10px] text-slate-400 font-medium italic">· 已编辑</span>
                </div>

                <div class="flex items-center gap-3">
                  <button 
                    @click="copyToClipboard(message.content)"
                    class="p-1 text-slate-500 dark:text-slate-400 hover:text-primary-600 transition-colors"
                    title="复制内容"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" /></svg>
                  </button>
                  <div v-if="!selectionMode && editingIndex !== index" class="flex items-center gap-2.5">
                    <button 
                      @click="startEdit(index, message.content)"
                      class="text-slate-500 dark:text-slate-400 hover:text-primary-600 transition-colors"
                      title="编辑重发"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                    </button>
                    <button 
                      @click="emit('resend', index)"
                      class="text-slate-500 dark:text-slate-400 hover:text-primary-600 transition-colors"
                      title="重新发送"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="isLoadingContent" class="w-full px-2 py-4">
          <div class="flex items-center gap-3 text-gray-400">
            <div class="flex gap-1.5">
              <span class="w-1.5 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full animate-pulse"></span>
              <span class="w-1.5 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full animate-pulse [animation-delay:200ms]"></span>
              <span class="w-1.5 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full animate-pulse [animation-delay:400ms]"></span>
            </div>
            <span class="text-[10px] font-bold tracking-widest uppercase">AI 正在思考中...</span>
          </div>
        </div>
      </template>

      <!-- Empty State -->
      <div v-if="messages.length === 0 && !isLoadingContent" class="flex-1 flex flex-col items-center justify-center opacity-30">
        <div class="w-12 h-12 mb-6 rounded-lg bg-slate-50 dark:bg-slate-900 flex items-center justify-center border border-slate-100 dark:border-slate-800">
          <svg class="w-6 h-6 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <p class="text-[10px] font-bold text-slate-400 uppercase tracking-[0.3em]">Ready for questions</p>
      </div>
    </div>
  </div>
</template>

<style>
/* Shadow Definitions - REMOVED refined and replaced with subtle border focus */

/* User Message Visual Texture */
.user-message-pattern {
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(59, 130, 246, 0.03) 11px,
    rgba(59, 130, 246, 0.03) 12px
  );
}
.assistant-message-light {
  border-bottom: none;
}
.dark .assistant-message-light {
  border-bottom: none;
}
.dark .user-message-pattern {
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 20px,
    rgba(255, 255, 255, 0.01) 21px,
    rgba(255, 255, 255, 0.01) 22px
  );
}

/* Markdown Style Overrides */
.markdown-body > :first-child { margin-top: 0 !important; }
.markdown-body > :last-child { margin-bottom: 0 !important; }
.markdown-body ul { list-style-type: disc; padding-left: 1.5em; }
.markdown-body ol { list-style-type: decimal; padding-left: 1.5em; }
.markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.markdown-body :not(pre) > code {
  background-color: rgba(100, 116, 139, 0.1);
  color: #eb5757;
  padding: 0.2rem 0.4rem;
  border-radius: 0.375rem;
  font-size: 0.85em;
  font-weight: 600;
}
.dark .markdown-body :not(pre) > code {
  background-color: rgba(255, 255, 255, 0.08);
  color: #ff7b72;
}
.citation-ref:hover { text-decoration: underline; }

/* Scrollbar Style */
::-webkit-scrollbar {
  width: 5px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #f1f1f1;
  border-radius: 10px;
}
.dark ::-webkit-scrollbar-thumb {
  background: #333;
}
::-webkit-scrollbar-thumb:hover {
  background: #e2e2e2;
}
</style>
