<script setup lang="ts">
import type { ChatSession } from '../../stores/chat'

const props = defineProps<{
  sessions: ChatSession[]
  currentSessionId?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'load-session', id: string): void
  (e: 'delete-session', id: string, event: Event): void
}>()

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<template>
  <div
    class="absolute inset-0 bg-black/20 z-20"
    @click="$emit('close')"
  >
    <div
      class="absolute right-0 top-0 bottom-0 w-80 bg-white/95 dark:bg-[#252526] backdrop-blur-md border-l border-gray-200/50 dark:border-gray-800/50"
      @click.stop
    >
      <!-- History Header -->
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
        <h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200 tracking-wide">聊天记录</h3>
        <button
          @click="$emit('close')"
          class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-all duration-200"
        >
          <svg class="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>

      <!-- History List -->
      <div class="overflow-y-auto" style="height: calc(100% - 65px)">
        <div v-if="sessions.length === 0" class="p-8 text-center text-gray-400 text-sm">暂无聊天记录</div>
        <div
          v-for="session in sessions"
          :key="session.id"
          class="relative group/item"
        >
          <button
            @click="$emit('load-session', session.id)"
            class="w-full text-left px-5 py-3.5 pr-12 hover:bg-gray-50/80 dark:hover:bg-[#2d2d30] border-b border-gray-50 dark:border-gray-800 transition-all duration-200"
            :class="{ 'bg-gray-50 dark:bg-[#2d2d30]': session.id === currentSessionId }"
          >
            <div class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate mb-1.5">{{ session.title }}</div>
            <div class="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
              <span>{{ session.messages.length }} 条消息</span>
              <span>{{ formatTime(session.updatedAt) }}</span>
            </div>
          </button>
          <button
            @click="$emit('delete-session', session.id, $event)"
            class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover/item:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all"
          >
            <svg class="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
