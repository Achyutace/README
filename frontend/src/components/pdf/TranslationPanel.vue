<script setup lang="ts">
/*
----------------------------------------------------------------------
                            翻译面板
----------------------------------------------------------------------
*/ 
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { usePdfStore } from '../../stores/pdf'
import { useTranslationStore } from '../../stores/translation'
import { useDraggableWindow } from '../../composables/useDraggableWindow'
import { useResizableWindow } from '../../composables/useResizableWindow'
import type { TranslationPanelInstance } from '../../types'
import { clamp } from '@vueuse/core'

const pdfStore = usePdfStore()
const translationStore = useTranslationStore()

// 常量定义
const TEXT_PANEL_ID = 'text-selection-panel'
const MIN_WIDTH = 280
const MAX_WIDTH = 900
const MIN_HEIGHT = 150
const MAX_HEIGHT = 600
const SIDEBAR_SNAP_THRESHOLD = 100
const PARAGRAPH_SNAP_THRESHOLD = 150
const DEFAULT_FONT_SIZE = 14
const MIN_FONT_SIZE = 12
const MAX_FONT_SIZE = 24

// 划词翻译面板的本地状态（因为 Store 中未存储其尺寸）
const textPanelSize = ref({ width: 320, height: 280 })

// 拖拽与缩放状态
const draggingPanelId = ref<string | null>(null)
const resizingPanelId = ref<string | null>(null)

// 吸附相关状态
const isNearSnapTarget = ref(false)
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null)
const snapTargetParagraphId = ref<string | null>(null)
const isNearSidebar = ref(false)

// 字体大小映射
const fontSizeMap: Record<string, number> = {}

// 复制状态映射
const copiedPanelId = ref<string | null>(null)

// ===========================================
// 计算属性：合并显示所有面板
// ===========================================
const visiblePanels = computed(() => {
  // 1. 获取所有非侧边栏停靠的段落面板
  const panels: Array<TranslationPanelInstance & { isTextPanel?: boolean }> = 
    translationStore.translationPanels.filter(p => !p.isSidebarDocked).map(p => ({ ...p, isTextPanel: false }))
  
  // 2. 如果划词翻译开启，添加划词翻译面板
  if (translationStore.showTextTranslation) {
    panels.push({
      id: TEXT_PANEL_ID,
      paragraphId: '', // 划词翻译无段落ID
      position: translationStore.textPanelPosition,
      size: textPanelSize.value,
      translation: translationStore.textTranslationResult || (translationStore.isTextTranslating ? '' : '暂无翻译'),
      isLoading: translationStore.isTextTranslating,
      originalText: '', 
      snapMode: 'none',
      snapTargetParagraphId: null,
      isSidebarDocked: false,
      isTextPanel: true
    })
  }
  
  return panels
})

// ===========================================
// 辅助功能
// ===========================================

function getFontSize(panelId: string): number {
  return fontSizeMap[panelId] || DEFAULT_FONT_SIZE
}

function increaseFontSize(panelId: string) {
  const current = getFontSize(panelId)
  if (current < MAX_FONT_SIZE) fontSizeMap[panelId] = current + 1
}

function decreaseFontSize(panelId: string) {
  const current = getFontSize(panelId)
  if (current > MIN_FONT_SIZE) fontSizeMap[panelId] = current - 1
}

async function copyTranslation(panel: any) {
  if (!panel.translation) return
  try {
    await navigator.clipboard.writeText(panel.translation)
    copiedPanelId.value = panel.id
    // 不再自动清除复制状态，让它一直显示
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

function closePanel(panelId: string) {
  if (panelId === TEXT_PANEL_ID) {
    translationStore.closeTextTranslation()
  } else {
    translationStore.closeTranslationPanelById(panelId)
  }
}

async function retranslate(panel: any) {
  if (panel.isTextPanel) {
    // 划词翻译重新翻译
    const originalText = translationStore.textTranslationOriginal
    if (!originalText) return
    await translationStore.translateText(originalText, true)
  } else {
    // 段落翻译重新翻译
    if (!panel.paragraphId) return
    translationStore.setPanelLoading(panel.id, true)
    const translation = await translationStore.translateParagraph(panel.paragraphId, true)
    if (translation) {
      translationStore.setTranslation(panel.paragraphId, translation)
    }
  }
}

function focusPanel(panelId: string) {
  if (panelId !== TEXT_PANEL_ID) {
    translationStore.bringPanelToFront(panelId)
  }
  // Text panel stays implicitly on top due to render order in computed
}

// ===========================================
// 拖拽逻辑 (Draggable)
// ===========================================

// 计算吸附位置
function calculateParagraphSnapPosition(paragraphId: string) {
  const paragraph = pdfStore.paragraphs.find(p => p.id === paragraphId)
  if (!paragraph) return null

  // 查找对应的段落 marker 元素
  const marker = document.querySelector(`[data-paragraph-id="${paragraphId}"]`) as HTMLElement
  if (!marker) return null

  const scaleFactor = pdfStore.scale
  const markerRect = marker.getBoundingClientRect()

  // 使用 marker 的位置作为段落左上角，计算段落的完整位置
  const left = markerRect.left
  const top = markerRect.top
  const width = paragraph.bbox.width * scaleFactor
  const height = paragraph.bbox.height * scaleFactor

  const pageElement = marker.closest('.pdf-page') as HTMLElement | null

  return { left, top, width, height, pageElement }
}

function getAllParagraphRects() {
  const results: Array<{ id: string; rect: { left: number; top: number; width: number; height: number }; page: number }> = []
  
  // 获取所有带有段落ID的元素
  const markers = document.querySelectorAll('[data-paragraph-id]')
  const scale = pdfStore.scale

  markers.forEach(marker => {
    const id = marker.getAttribute('data-paragraph-id')
    if (!id) return
    
    // 查找 store 中的段落数据
    const paragraph = pdfStore.paragraphs.find(p => p.id === id)
    if (!paragraph) return

    // 获取 marker 的位置作为参考点
    // marker 位于段落的左上角 (x0, y0)
    const markerRect = marker.getBoundingClientRect()
    
    // 计算段落在视口中的位置
    // 使用 marker 作为 (x0, y0) 参考点，然后计算整个 bbox
    const left = markerRect.left
    const top = markerRect.top
    const width = paragraph.bbox.width * scale
    const height = paragraph.bbox.height * scale

    results.push({
      id,
      rect: { left, top, width, height },
      page: paragraph.page
    })
  })
  
  return results
}

const { startDrag: initDrag, setPosition: setDragPosition } = useDraggableWindow({
  onDrag: (newPos) => {
    if (!draggingPanelId.value) return
    const currentId = draggingPanelId.value

    // --- 1. 划词翻译面板处理 ---
    if (currentId === TEXT_PANEL_ID) {
       const maxX = window.innerWidth - textPanelSize.value.width
       const maxY = window.innerHeight - textPanelSize.value.height
       translationStore.updateTextPanelPosition({
          x: clamp(newPos.x, 0, maxX),
          y: clamp(newPos.y, 0, maxY)
       })
       // 划词翻译不支持吸附逻辑
       return
    }

    // --- 2. 段落翻译面板处理 ---
    const panel = translationStore.translationPanels.find(p => p.id === currentId)
    if (!panel) {
      console.warn(`Translation panel ${currentId} not found during drag`)
      return
    }
    
    // 吸附检测逻辑
    const distanceToRight = window.innerWidth - (newPos.x + panel.size.width)
    isNearSidebar.value = distanceToRight < SIDEBAR_SNAP_THRESHOLD
    
    if (!isNearSidebar.value) {
      // 检测附近段落
      const allParagraphs = getAllParagraphRects()
      let nearest: { id: string; distance: number; rect: { left: number; top: number; width: number; height: number } } | null = null
      
      const panelCx = newPos.x + panel.size.width / 2
      const panelCy = newPos.y + panel.size.height / 2

      for (const p of allParagraphs) {
        // 优先判断：面板中心点是否在段落 Rect 内部
        const isInside = 
          panelCx >= p.rect.left && 
          panelCx <= p.rect.left + p.rect.width &&
          panelCy >= p.rect.top &&
          panelCy <= p.rect.top + p.rect.height

        if (isInside) {
          nearest = { id: p.id, distance: 0, rect: p.rect }
          break // 找到直接吸附
        }

        // 备选逻辑：计算中心点距离
        const markerCx = p.rect.left + p.rect.width / 2
        const markerCy = p.rect.top + p.rect.height / 2
        
        const dist = Math.hypot(panelCx - markerCx, panelCy - markerCy)
        if (dist < PARAGRAPH_SNAP_THRESHOLD) {
           if (!nearest || (nearest.distance > 0 && dist < nearest.distance)) {
             nearest = { id: p.id, distance: dist, rect: p.rect }
           }
        }
      }

      if (nearest) {
        isNearSnapTarget.value = true
        snapTargetParagraphId.value = nearest.id
        // 直接使用计算好的 nearest.rect，避免二次计算
        snapTargetRect.value = nearest.rect
      } else {
        isNearSnapTarget.value = false
        snapTargetParagraphId.value = null
        snapTargetRect.value = null
      }
    } else {
      isNearSnapTarget.value = false
      snapTargetParagraphId.value = null
      snapTargetRect.value = null
    }

    // 限制在窗口内并更新 store
    const maxX = window.innerWidth - panel.size.width
    const maxY = window.innerHeight - panel.size.height
    translationStore.updatePanelPosition(currentId, {
      x: clamp(newPos.x, 0, maxX),
      y: clamp(newPos.y, 0, maxY)
    })
  },
  onDragEnd: () => {
    if (draggingPanelId.value && draggingPanelId.value !== TEXT_PANEL_ID) {
        // 应用吸附/停靠
        if (isNearSidebar.value) {
            translationStore.setPanelSnapMode(draggingPanelId.value, 'sidebar')
        } else if (isNearSnapTarget.value && snapTargetRect.value && snapTargetParagraphId.value) {
             translationStore.setPanelSnapMode(draggingPanelId.value, 'paragraph', snapTargetParagraphId.value)
             translationStore.updatePanelPosition(draggingPanelId.value, {
                 x: snapTargetRect.value.left,
                 y: snapTargetRect.value.top
             })
             // 同时调整宽度以匹配段落
             const panel = translationStore.translationPanels.find(p => p.id === draggingPanelId.value)
             if (panel) {
                translationStore.updatePanelSize(draggingPanelId.value, {
                    width: clamp(snapTargetRect.value.width, MIN_WIDTH, MAX_WIDTH),
                    height: panel.size.height
                })
             } else if (draggingPanelId.value) {
                console.warn(`Panel ${draggingPanelId.value} not found when applying snap resize`)
             }
        }
    }
    // 重置状态
    draggingPanelId.value = null
    isNearSnapTarget.value = false
    isNearSidebar.value = false
    snapTargetRect.value = null
    snapTargetParagraphId.value = null
  }
})

function startDrag(e: MouseEvent, panelId: string) {
  if (!(e.target as HTMLElement).closest('.panel-header')) return
  
  draggingPanelId.value = panelId
  
  if (panelId === TEXT_PANEL_ID) {
    setDragPosition(translationStore.textPanelPosition)
  } else {
    const panel = translationStore.translationPanels.find(p => p.id === panelId)
    if (!panel) {
      console.warn(`Translation panel ${panelId} not found when starting drag`)
      return
    }
    setDragPosition(panel.position)
    translationStore.setPanelSnapMode(panelId, 'none')
    translationStore.bringPanelToFront(panelId)
  }
  
  initDrag(e)
}

// ===========================================
// 缩放逻辑 (Resizable)
// ===========================================

const { startResize: initResize, setSize: setResizeSize } = useResizableWindow({
  minWidth: MIN_WIDTH, maxWidth: MAX_WIDTH, minHeight: MIN_HEIGHT, maxHeight: MAX_HEIGHT,
  onResize: ({ size, delta }) => {
    if (!resizingPanelId.value) return
    const id = resizingPanelId.value

    // 1. 划词翻译面板
    if (id === TEXT_PANEL_ID) {
        textPanelSize.value = size
        if (delta.x !== 0 || delta.y !== 0) {
            const curPos = translationStore.textPanelPosition
            translationStore.updateTextPanelPosition({
                x: curPos.x + delta.x,
                y: curPos.y + delta.y
            })
        }
        return
    }

    // 2. 段落翻译面板
    const panel = translationStore.translationPanels.find(p => p.id === id)
    if (!panel) {
      console.warn(`Translation panel ${id} not found during resize`)
      return
    }

    translationStore.updatePanelSize(id, size)
    if (delta.x !== 0 || delta.y !== 0) {
       translationStore.updatePanelPosition(id, {
        x: panel.position.x + delta.x,
        y: panel.position.y + delta.y
      })
    }
  },
  onResizeEnd: () => {
    resizingPanelId.value = null
  }
})

function startResize(e: MouseEvent, panelId: string, direction: string) {
  resizingPanelId.value = panelId
  
  if (panelId === TEXT_PANEL_ID) {
    setResizeSize(textPanelSize.value)
  } else {
    const panel = translationStore.translationPanels.find(p => p.id === panelId)
    if (!panel) {
      console.warn(`Translation panel ${panelId} not found when starting resize`)
      return
    }
    setResizeSize(panel.size)
    translationStore.bringPanelToFront(panelId)
  }
  
  initResize(e, direction)
}

// ===========================================
// PDF滚动与更新逻辑
// ===========================================

// 自动请求翻译（仅针对段落面板）
async function fetchTranslation(panel: TranslationPanelInstance) {
  if (!panel.paragraphId || panel.translation) return

  // 优先从内存缓存取（全文翻译/按页翻译已写入），命中则直接填充，无需再发请求
  const cached = translationStore.getCachedTranslation(panel.paragraphId)
  if (cached) {
    translationStore.setTranslation(panel.paragraphId, cached)
    return
  }

  translationStore.setPanelLoading(panel.id, true)
  const translation = await translationStore.translateParagraph(panel.paragraphId)
  if (translation) {
    translationStore.setTranslation(panel.paragraphId, translation)
  } else {
    translationStore.setTranslation(panel.paragraphId, '翻译失败，请重试')
  }
}

watch(() => translationStore.translationPanels.length, () => {
  translationStore.translationPanels.forEach(panel => {
    if (!panel.translation && panel.isLoading) {
      fetchTranslation(panel)
    }
  })
}, { immediate: true })

// 滚动同步
function updateSnappedPanelPositions() {
  translationStore.translationPanels.forEach(panel => {
    if (panel.snapMode === 'paragraph' && panel.snapTargetParagraphId) {
      const snapPos = calculateParagraphSnapPosition(panel.snapTargetParagraphId)
      if (snapPos) {
        translationStore.updatePanelPosition(panel.id, {
          x: snapPos.left,
          y: snapPos.top
        })
        translationStore.updatePanelSize(panel.id, {
          width: clamp(snapPos.width, MIN_WIDTH, MAX_WIDTH),
          height: panel.size.height
        })
      }
    }
  })
}

const debouncedUpdatePositions = useDebounceFn(updateSnappedPanelPositions, 16)
let scrollRafId: number | null = null

function onPdfScroll() {
  if (scrollRafId) cancelAnimationFrame(scrollRafId)
  scrollRafId = requestAnimationFrame(() => {
    updateSnappedPanelPositions()
    scrollRafId = null
  })
}

// 容器绑定监听
let pdfContainerRef: Element | null = null
let resizeObserver: ResizeObserver | null = null
let bindRetryCount = 0
const MAX_BIND_RETRIES = 10

function bindScrollListener() {
  if (pdfContainerRef) return
  pdfContainerRef = document.querySelector('.pdf-scroll-container')
  if (pdfContainerRef) {
    pdfContainerRef.addEventListener('scroll', onPdfScroll, { passive: true })
    resizeObserver = new ResizeObserver(() => debouncedUpdatePositions())
    resizeObserver.observe(pdfContainerRef)
    bindRetryCount = 0
  } else if (bindRetryCount < MAX_BIND_RETRIES) {
    bindRetryCount++
    setTimeout(bindScrollListener, 200)
  }
}

watch(() => pdfStore.currentPdfUrl, () => {
  if (pdfContainerRef) {
    pdfContainerRef.removeEventListener('scroll', onPdfScroll)
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    pdfContainerRef = null
  }
  bindRetryCount = 0
  setTimeout(bindScrollListener, 200)
}, { immediate: true })

onMounted(() => {
  setTimeout(bindScrollListener, 200)
})

onBeforeUnmount(() => {
  if (pdfContainerRef) {
    pdfContainerRef.removeEventListener('scroll', onPdfScroll)
    pdfContainerRef = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (scrollRafId) {
    cancelAnimationFrame(scrollRafId)
  }
})
</script>

<template>
  <!-- 拖动时显示的吸附提示 -->
  <div
    v-if="draggingPanelId && draggingPanelId !== TEXT_PANEL_ID && snapTargetRect && isNearSnapTarget"
    class="snap-hint fixed z-[998] pointer-events-none"
    :style="{
      left: snapTargetRect.left + 'px',
      top: snapTargetRect.top + 'px',
      width: snapTargetRect.width + 'px',
      height: snapTargetRect.height + 'px',
    }"
  >
    <div class="snap-hint-text">释放以吸附</div>
  </div>
  
  <!-- 侧边栏吸附提示 -->
  <div
    v-if="draggingPanelId && draggingPanelId !== TEXT_PANEL_ID && isNearSidebar"
    class="sidebar-snap-hint fixed z-[998] pointer-events-none right-0 top-0 bottom-0 w-16"
  >
    <div class="sidebar-hint-text">停靠到侧边栏</div>
  </div>

  <!-- 渲染所有翻译面板 -->
  <template v-for="(panel, index) in visiblePanels" :key="panel.id">
    <div
      class="translation-panel fixed rounded-lg overflow-hidden select-none"
      :class="{ 
        'is-snapped': panel.snapMode === 'paragraph',
        'is-dragging': draggingPanelId === panel.id,
        'is-text-panel': panel.isTextPanel // 辅助类
      }"
      :style="{
        left: panel.position.x + 'px',
        top: panel.position.y + 'px',
        width: panel.size.width + 'px',
        height: panel.size.height + 'px',
        zIndex: 1000 + index
      }"
      @mousedown="focusPanel(panel.id)"
    >
      <!-- 头部 -->
      <div 
        class="panel-header flex items-center justify-between px-2 py-1 cursor-move"
        @mousedown="startDrag($event, panel.id)"
      >
        <div class="flex items-center gap-1.5">
          <span class="text-xs font-medium text-gray-600 dark:text-gray-400">
            {{ panel.isTextPanel ? '划词翻译' : 'AI 译文' }}
          </span>
          <span v-if="panel.snapMode === 'paragraph'" class="text-[10px] text-gray-400 dark:text-gray-500">· 已吸附</span>
        </div>
        <div class="flex items-center gap-0.5">
          <!-- 复制按钮 -->
          <button
            @click.stop="copyTranslation(panel)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            :title="copiedPanelId === panel.id ? '已复制' : '复制译文'"
            :disabled="panel.isLoading || !panel.translation"
          >
            <svg v-if="copiedPanelId === panel.id" class="w-3 h-3 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <svg v-else class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke-width="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke-width="2" />
            </svg>
          </button>
          
          <!-- 字体大小控制 -->
          <button @click.stop="decreaseFontSize(panel.id)" class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors" title="减小字体">
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
            </svg>
          </button>
          <button @click.stop="increaseFontSize(panel.id)" class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors" title="增大字体">
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          
          <!-- 重新翻译 -->
          <button
            @click.stop="retranslate(panel)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="重新翻译"
            :disabled="panel.isLoading"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" :class="{ 'animate-spin': panel.isLoading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          
          <!-- 关闭 -->
          <button
            @click.stop="closePanel(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="关闭"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      
      <!-- 内容区域 -->
      <div class="panel-content flex-1 overflow-y-auto p-3 cursor-auto select-text" @mousedown.stop>
        <div v-if="panel.isLoading" class="flex flex-col items-center justify-center py-6">
          <div class="loading-spinner mb-2"></div>
          <span class="text-gray-400 dark:text-gray-500 text-xs">翻译中...</span>
        </div>

        <div
          v-else
          class="translation-text text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap"
          :style="{ fontSize: getFontSize(panel.id) + 'px' }"
        >
          {{ panel.translation || '暂无翻译' }}
        </div>
      </div>
      
      <!-- 调整大小的边框 (TextPanel也允许调整) -->
      <template v-if="!panel.isSidebarDocked">
        <div class="resize-handle resize-w" @mousedown="startResize($event, panel.id, 'w')"></div>
        <div class="resize-handle resize-e" @mousedown="startResize($event, panel.id, 'e')"></div>
        <div class="resize-handle resize-s" @mousedown="startResize($event, panel.id, 's')"></div>
        <div class="resize-handle resize-sw" @mousedown="startResize($event, panel.id, 'sw')"></div>
        <div class="resize-handle resize-se" @mousedown="startResize($event, panel.id, 'se')"></div>
      </template>
    </div>
  </template>
</template>

<style scoped>
.translation-panel {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.dark .translation-panel {
  background: #1e1e1e;
  border-color: #121726;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3);
}

.panel-header {
  height: 24px;
  background: linear-gradient(to right, #e8eef3, #dfe6ed);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.dark .panel-header {
  background: #252526;
  border-bottom-color: #121726;
}

.translation-panel.is-snapped {
  border: 1px solid rgba(120, 140, 160, 0.3);
}

.dark .translation-panel.is-snapped {
  border-color: rgba(140, 160, 180, 0.2);
}

.translation-panel.is-dragging {
  opacity: 0.9;
  cursor: grabbing;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #9ca3af;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.dark .loading-spinner {
  border-color: #374151;
  border-top-color: #6b7280;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.panel-content::-webkit-scrollbar { width: 4px; }
.panel-content::-webkit-scrollbar-track { background: transparent; }
.panel-content::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }
.panel-content::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
.dark .panel-content::-webkit-scrollbar-thumb { background: #4b5563; }
.dark .panel-content::-webkit-scrollbar-thumb:hover { background: #6b7280; }

.resize-handle { position: absolute; background: transparent; }
.resize-w { left: 0; top: 24px; bottom: 6px; width: 4px; cursor: ew-resize; }
.resize-e { right: 0; top: 24px; bottom: 6px; width: 4px; cursor: ew-resize; }
.resize-s { bottom: 0; left: 6px; right: 6px; height: 4px; cursor: ns-resize; }
.resize-sw { left: 0; bottom: 0; width: 8px; height: 8px; cursor: nesw-resize; }
.resize-se { right: 0; bottom: 0; width: 8px; height: 8px; cursor: nwse-resize; }
.resize-handle:hover { background: rgba(120, 140, 160, 0.1); }

.snap-hint {
  border: 2px dashed rgba(59, 130, 246, 0.6);
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.1);
  transition: all 0.15s ease;
  animation: snap-pulse 1s ease-in-out infinite;
}
@keyframes snap-pulse { 0%, 100% { opacity: 0.8; } 50% { opacity: 1; } }

.snap-hint-text {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px; font-weight: 500;
  border-radius: 4px; white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.sidebar-snap-hint {
  background: linear-gradient(to left, rgba(59, 130, 246, 0.15), transparent);
  border-left: 2px dashed rgba(59, 130, 246, 0.5);
}

.sidebar-hint-text {
  position: absolute; top: 50%; right: 16px;
  transform: translateY(-50%) rotate(-90deg);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px; font-weight: 500;
  border-radius: 4px; white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
</style>
