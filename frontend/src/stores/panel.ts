import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { AiPanelTab } from '../types'

export const usePanelStore = defineStore('panel', () => {
    // 面板标签定义
    const tabs: AiPanelTab[] = [
        { id: 'roadmap', label: 'Roadmap', icon: 'map' },
        { id: 'translation', label: 'Translation', icon: 'translate' },
    ]
    const activeTab = ref<AiPanelTab['id']>((localStorage.getItem('readme_active_tab') as AiPanelTab['id']) || 'roadmap')
    const isPanelHidden = ref(localStorage.getItem('readme_panel_hidden') === 'true')

    watch(activeTab, (val) => localStorage.setItem('readme_active_tab', val))
    watch(isPanelHidden, (val) => localStorage.setItem('readme_panel_hidden', String(val)))

    // 消息选择模式
    const selectionMode = ref(false)
    const selectedMessageIds = ref<Set<string>>(new Set())

    // 切换当前激活的 tab
    function setActiveTab(tabId: AiPanelTab['id']) {
        activeTab.value = tabId
    }

    // 折叠/展开侧边面板
    function togglePanel() {
        isPanelHidden.value = !isPanelHidden.value
    }

    // -----------------------------
    // 消息选择相关
    // -----------------------------
    function toggleSelectionMode() {
        selectionMode.value = !selectionMode.value
        if (!selectionMode.value) {
            selectedMessageIds.value = new Set()
        }
    }

    function toggleMessageSelection(id: string) {
        const newSet = new Set(selectedMessageIds.value)
        if (newSet.has(id)) {
            newSet.delete(id)
        } else {
            newSet.add(id)
        }
        selectedMessageIds.value = newSet
    }

    return {
        tabs,
        activeTab,
        isPanelHidden,
        selectionMode,
        selectedMessageIds,
        setActiveTab,
        togglePanel,
        toggleSelectionMode,
        toggleMessageSelection
    }
})
