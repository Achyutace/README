import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Roadmap } from '../types'
import { aiApi } from '../api'

export const useRoadmapStore = defineStore('roadmap', () => {
    const roadmap = ref<Roadmap | null>(null)
    const isLoadingRoadmap = ref(false)

    // 简单的自动布局函数：为没有 position 的节点生成网格布局
    function layoutNodes(data: Roadmap): Roadmap {
        if (data.nodes.some(n => n.position && (n.position.x !== 0 || n.position.y !== 0))) {
            return data;
        }
        const nodes = data.nodes.map((node, index) => ({
            ...node,
            position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 150 },
            data: node.data // 保持原有 data
        }))
        return { ...data, nodes }
    }

    function setRoadmap(newRoadmap: Roadmap | null) {
        roadmap.value = newRoadmap
    }

    async function fetchRoadmap(pdfId: string) {
        if (roadmap.value) return

        isLoadingRoadmap.value = true
        try {
            const data = await aiApi.generateRoadmap(pdfId)
            const processedRoadmap = layoutNodes(data)
            setRoadmap(processedRoadmap)
        } catch (error) {
            console.error('Error fetching roadmap:', error)
            throw error
        } finally {
            isLoadingRoadmap.value = false
        }
    }

    function resetForNewDocument() {
        roadmap.value = null
    }

    function clearAllData() {
        roadmap.value = null
    }

    return {
        roadmap,
        isLoadingRoadmap,
        setRoadmap,
        fetchRoadmap,
        resetForNewDocument,
        clearAllData
    }
})
