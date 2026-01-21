<script setup lang="ts">
import { useAiStore } from '../../stores/ai'
import RoadmapTab from './RoadmapTab.vue'
import SummaryTab from './SummaryTab.vue'
import TranslationTab from './TranslationTab.vue'


const aiStore = useAiStore()
</script>

<template>
  <div class="h-full bg-white flex flex-col">
    <!-- Tab Navigation (no header, handled by parent) -->
    <div class="border-b border-gray-200">
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
  </div>
</template>
