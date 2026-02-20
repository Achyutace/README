<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useMarkdownRenderer } from '../../composables/useMarkdownRenderer'
import type { ChatMessage, Citation } from '../../types'

const props = defineProps<{
  messages: ChatMessage[]
  isLoadingContent: boolean
}>()

const emit = defineEmits<{
  (e: 'click-citation', citations: Citation[], event: MouseEvent): void
}>()

const { tooltipState, renderMarkdown, handleMessageMouseOver, handleMessageMouseOut, handleMessageClick, handleTooltipEnter, handleTooltipLeave } = useMarkdownRenderer()

const messagesContainer = ref<HTMLElement | null>(null)

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

defineExpose({
  scrollToBottom
})
</script>

<template>
  <div class="h-full flex flex-col relative w-full overflow-hidden">
    <!-- Tooltip Component (Global Absolute Position within List) -->
    <div 
      v-if="tooltipState.visible && tooltipState.content"
      class="fixed z-[100] w-80 bg-white dark:bg-[#2d2d30] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 p-4 transition-opacity duration-200"
      :style="{ left: Math.min(tooltipState.x - 20, 1024) + 'px', top: (tooltipState.y - 10) + 'px', transform: 'translateY(-100%)' }"
      @mouseenter="handleTooltipEnter"
      @mouseleave="handleTooltipLeave"
    >
      <!-- Header: Icon + Type -->
      <div class="flex items-center gap-2 mb-2 text-xs font-bold uppercase tracking-wider text-gray-400">
        <span v-if="tooltipState.content.source_type === 'local'" class="flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          本地文档 - P{{ tooltipState.content.page || 'N/A' }}
        </span>
        <span v-else class="flex items-center gap-1 text-blue-500">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
          网络来源
        </span>
      </div>

      <!-- Title -->
      <h4 class="font-semibold text-sm text-gray-800 dark:text-gray-100 mb-2 leading-tight">
        {{ tooltipState.content.title }}
      </h4>

      <!-- Snippet -->
      <p class="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-black/20 p-2 rounded mb-2 border-l-2 border-primary-400 line-clamp-4 italic">
        "{{ tooltipState.content.snippet }}"
      </p>

      <!-- Action Hint -->
      <div v-if="tooltipState.content.source_type === 'external'" class="text-xs text-blue-600 dark:text-blue-400 flex items-center justify-end gap-1 mt-2">
        点击跳转原文 <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
      </div>
    </div>

    <!-- Messages Area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto w-full p-4 space-y-6">
      <template v-if="messages.length > 0">
        <div v-for="message in messages" :key="message.id" :class="[message.role === 'user' ? 'max-w-[85%] ml-auto' : 'w-full']">
          
          <!-- User Message -->
          <div v-if="message.role === 'user'" class="px-5 py-3.5 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100/80 dark:from-[#2d2d30] dark:to-[#3e3e42] text-gray-800 dark:text-gray-200 rounded-br-md border border-gray-100/50 dark:border-gray-700/50 shadow-sm">
            <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>
          </div>
          
          <!-- Assistant Message -->
          <div v-else class="space-y-4 pl-1 pr-4">
            <!-- 1. Content with Citations -->
            <div 
              class="markdown-body prose prose-sm max-w-none dark:prose-invert 
                     prose-p:leading-relaxed prose-pre:bg-[#282c34] prose-pre:m-0
                     prose-headings:font-semibold prose-headings:text-gray-800 dark:prose-headings:text-gray-100
                     prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                     text-gray-800 dark:text-gray-200"
              v-html="renderMarkdown(message.content)"
              @mouseover="handleMessageMouseOver($event, message.citations || [])"
              @mouseout="handleMessageMouseOut"
              @click="onCitationClick($event, message.citations || [])"
            ></div>
            
            <!-- 2. Structured Reference List (Bottom) -->
            <div v-if="message.citations && message.citations.length > 0" class="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/50">
              <h4 class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">参考来源</h4>
              <div class="grid grid-cols-1 gap-2">
                <div 
                  v-for="cite in message.citations" 
                  :key="cite.id"
                  class="flex items-start gap-3 p-2 rounded-lg border border-transparent hover:border-gray-200 dark:hover:border-gray-700 hover:bg-gray-50 dark:hover:bg-[#3e3e42] transition-colors group"
                >
                  <!-- Index Badge -->
                  <div class="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[10px] font-bold text-primary-600 bg-primary-50 rounded mt-0.5">
                    {{ cite.id }}
                  </div>
                  
                  <!-- Content -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <span v-if="cite.source_type === 'local'" class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">PDF</span>
                      <span v-else class="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">Web</span>
                      
                      <a 
                        v-if="cite.source_type === 'external' && cite.url"
                        :href="cite.url" 
                        target="_blank"
                        class="text-xs font-medium text-gray-800 dark:text-gray-200 hover:text-blue-600 dark:hover:text-blue-400 truncate block"
                      >
                        {{ cite.title }}
                      </a>
                      <span v-else class="text-xs font-medium text-gray-800 dark:text-gray-200 truncate block">
                        {{ cite.title }}
                      </span>
                    </div>
                    
                    <p class="text-xs text-gray-400 truncate">
                      {{ cite.snippet }}
                    </p>
                  </div>

                  <!-- Action Icon (External Link) -->
                  <a 
                     v-if="cite.source_type === 'external' && cite.url"
                     :href="cite.url"
                     target="_blank"
                     class="flex-shrink-0 text-gray-300 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                     title="打开链接"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
          
          <p class="text-xs text-gray-400 mt-1 px-1" :class="message.role === 'user' ? 'text-right' : ''">
            {{ new Date(message.timestamp).toLocaleTimeString() }}
          </p>
        </div>
        
        <div v-if="isLoadingContent" class="flex items-center gap-2 text-gray-500 p-4">
          <div class="flex gap-1"><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-75"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-150"></span></div>
          <span class="text-sm">正在深度思考...</span>
        </div>
      </template>

      <!-- #3: 空消息引导占位 -->
      <div v-if="messages.length === 0 && !isLoadingContent" class="flex-1 flex items-center justify-center">
        <div class="text-center px-8 py-12">
          <svg class="w-12 h-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p class="text-sm font-medium text-gray-400 dark:text-gray-500 mb-1">输入问题开始问答</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 自定义 Markdown 样式微调 */
.markdown-body > :first-child { margin-top: 0 !important; }
.markdown-body > :last-child { margin-bottom: 0 !important; }
.markdown-body ul { list-style-type: disc; padding-left: 1.5em; }
.markdown-body ol { list-style-type: decimal; padding-left: 1.5em; }
.markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.markdown-body :not(pre) > code {
  background-color: rgba(100, 116, 139, 0.1);
  color: #eb5757;
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
  font-size: 0.875em;
}
.dark .markdown-body :not(pre) > code {
  background-color: rgba(255, 255, 255, 0.1);
  color: #ff7b72;
}
.citation-ref:hover { text-decoration: underline; }
</style>
