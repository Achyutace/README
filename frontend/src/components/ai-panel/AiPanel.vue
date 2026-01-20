<script setup lang="ts">
import { useAiStore } from '../../stores/ai'
import RoadmapTab from './RoadmapTab.vue'
import SummaryTab from './SummaryTab.vue'
import TranslationTab from './TranslationTab.vue'


const aiStore = useAiStore()
</script>

<template>
  <aside class="w-96 h-full bg-white border-l border-gray-200 flex flex-col">
    <!-- Header with Tabs -->
    <div class="border-b border-gray-200">
      <div class="flex items-center justify-between px-4 py-3">
        <h2 class="text-lg font-semibold text-gray-800">AI 助手</h2>
        <button
          @click="aiStore.togglePanel"
          class="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          title="收起面板"
        >
          <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <!-- Tab Navigation -->
      <div class="flex px-2">
        <button
          v-for="tab in aiStore.tabs"
          :key="tab.id"
          @click="aiStore.setActiveTab(tab.id)"
          :class="[
            'flex-1 px-3 py-2 text-sm font-medium transition-colors border-b-2',
            aiStore.activeTab === tab.id
              ? 'text-primary-600 border-primary-600'
              : 'text-gray-500 border-transparent hover:text-gray-700 hover:border-gray-300'
          ]"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- Tab Content -->
    <div class="flex-1 overflow-hidden">
      <RoadmapTab v-if="aiStore.activeTab === 'roadmap'" />
      <SummaryTab v-else-if="aiStore.activeTab === 'summary'" />
      <TranslationTab v-else-if="aiStore.activeTab === 'translation'" />
    </div>
  </aside>
</template>
