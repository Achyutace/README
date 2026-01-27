<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、工具函数以及所需的 store 和 API
import { ref, onMounted, onBeforeUnmount, watch } from 'vue' // 导入Vue的响应式API和生命周期钩子
import { useDebounceFn } from '@vueuse/core' // 导入防抖函数
import { usePdfStore } from '../../stores/pdf' // 导入PDF store
import { aiApi } from '../../api' // 导入AI API
import { useLibraryStore } from '../../stores/library' // 导入文库 store
import type { TranslationPanelInstance } from '../../types' // 导入翻译面板实例类型

const pdfStore = usePdfStore() // 获取PDF store实例，用于管理PDF相关状态
const libraryStore = useLibraryStore() // 获取文库 store实例，用于管理文档库状态

// 当前拖动的面板
const draggingPanelId = ref<string | null>(null) // 当前正在拖动的面板ID，null表示没有拖动
const dragOffset = ref({ x: 0, y: 0 }) // 拖动时的偏移量，用于计算新位置

// 调整大小相关
const resizingPanelId = ref<string | null>(null) // 当前正在调整大小的面板ID
const resizeDirection = ref<string>('') // 调整大小的方向，如'e'东向，'w'西向等
const resizeStart = ref({ x: 0, y: 0, width: 0, height: 0 }) // 调整大小开始时的鼠标位置和面板尺寸

// 吸附相关
const isNearSnapTarget = ref(false) // 是否接近吸附目标（段落）
const snapTargetRect = ref<{ left: number; top: number; width: number; height: number } | null>(null) // 吸附目标的矩形区域
const snapTargetParagraphId = ref<string | null>(null) // 吸附目标段落的ID
const isNearSidebar = ref(false) // 是否接近侧边栏

// 字体大小管理
const fontSizeMap: Record<string, number> = {} // panelId -> fontSize 映射，存储每个面板的字体大小
const DEFAULT_FONT_SIZE = 14 // 默认字体大小
const MIN_FONT_SIZE = 12 // 最小字体大小
const MAX_FONT_SIZE = 24 // 最大字体大小

// 复制状态
const copiedPanelId = ref<string | null>(null) // 最近复制翻译内容的面板ID，用于显示复制成功状态

// 复制翻译内容到剪贴板
async function copyTranslation(panel: TranslationPanelInstance) { // 异步函数，复制指定面板的翻译内容
  if (!panel.translation) return // 如果没有翻译内容，直接返回

  try {
    await navigator.clipboard.writeText(panel.translation) // 将翻译内容写入系统剪贴板
    copiedPanelId.value = panel.id // 设置复制状态为当前面板ID
    // 2秒后重置状态，清除复制成功提示
    setTimeout(() => {
      if (copiedPanelId.value === panel.id) { // 检查是否还是同一个面板，避免多面板同时复制时的冲突
        copiedPanelId.value = null // 重置复制状态
      }
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err) // 复制失败时记录错误信息
  }
}

// 获取指定面板的字体大小
function getFontSize(panelId: string): number { // 返回面板的当前字体大小
  return fontSizeMap[panelId] || DEFAULT_FONT_SIZE // 从映射中获取，或返回默认值
}

// 增加指定面板的字体大小
function increaseFontSize(panelId: string) { // 增大字体
  const current = getFontSize(panelId) // 获取当前字体大小
  if (current < MAX_FONT_SIZE) { // 如果小于最大值
    fontSizeMap[panelId] = current + 1 // 增加1px
  }
}

// 减少指定面板的字体大小
function decreaseFontSize(panelId: string) { // 减小字体
  const current = getFontSize(panelId) // 获取当前字体大小
  if (current > MIN_FONT_SIZE) { // 如果大于最小值
    fontSizeMap[panelId] = current - 1 // 减少1px
  }
}

// 面板尺寸限制常量
const MIN_WIDTH = 280 // 最小面板宽度
const MAX_WIDTH = 900 // 最大面板宽度
const MIN_HEIGHT = 150 // 最小面板高度
const MAX_HEIGHT = 600 // 最大面板高度
const SIDEBAR_SNAP_THRESHOLD = 100 // 侧边栏吸附阈值距离（像素）
const PARAGRAPH_SNAP_THRESHOLD = 150 // 段落吸附阈值距离（像素）

// 获取所有可吸附的段落位置信息
function getAllParagraphRects(): Array<{ id: string; rect: DOMRect; page: number }> { // 返回所有段落的矩形信息数组
  const results: Array<{ id: string; rect: DOMRect; page: number }> = [] // 初始化结果数组
  const markers = document.querySelectorAll('[data-paragraph-id]') // 查找所有带有段落ID属性的元素
  markers.forEach(marker => { // 遍历每个标记元素
    const id = marker.getAttribute('data-paragraph-id') // 获取段落ID
    if (id) { // 如果ID存在
      const pageEl = marker.closest('.pdf-page') // 找到最近的PDF页面元素
      const page = pageEl ? Number(pageEl.getAttribute('data-page')) : 0 // 获取页面号
      results.push({ id, rect: marker.getBoundingClientRect(), page }) // 添加到结果数组
    }
  })
  return results // 返回段落信息数组
}

// 计算指定段落的吸附位置，实现精准覆盖原文
function calculateParagraphSnapPosition(paragraphId: string) { // 根据段落ID计算吸附位置
  const paragraphs = pdfStore.paragraphs // 获取所有段落数据
  const paragraph = paragraphs.find(p => p.id === paragraphId) // 查找指定段落
  if (!paragraph) return null // 如果没找到段落，返回null

  const pageElement = document.querySelector(`.pdf-page[data-page="${paragraph.page}"]`) as HTMLElement // 找到段落所在页面元素
  if (!pageElement) return null // 如果页面元素不存在，返回null

  const pageRect = pageElement.getBoundingClientRect() // 获取页面元素的边界矩形

  // 直接使用 pdfStore.scale 作为缩放因子
  const scaleFactor = pdfStore.scale // 获取当前PDF缩放因子

  // bbox坐标是相对于原始PDF尺寸（scale=1）的绝对坐标
  // 需要乘以当前缩放因子得到当前渲染尺寸下的坐标
  // pageRect.left/top 是页面在屏幕上的位置（会随滚动变化）
  const left = pageRect.left + (paragraph.bbox.x0 * scaleFactor) // 计算段落在屏幕上的左边距
  const top = pageRect.top + (paragraph.bbox.y0 * scaleFactor) // 计算段落在屏幕上的上边距
  const width = paragraph.bbox.width * scaleFactor // 计算段落的宽度
  const height = paragraph.bbox.height * scaleFactor // 计算段落的高度

  return { // 返回吸附位置信息
    left,
    top,
    width,
    height,
    pageElement
  }
}

// 开始拖动指定面板
function startDrag(e: MouseEvent, panelId: string) { // 鼠标按下时开始拖动
  if (!(e.target as HTMLElement).closest('.panel-header')) return // 只允许从面板头部拖动
  
  const panel = pdfStore.translationPanels.find(p => p.id === panelId) // 查找要拖动的面板
  if (!panel) return // 如果面板不存在，返回
  
  draggingPanelId.value = panelId // 设置当前拖动面板ID
  dragOffset.value = { // 计算拖动偏移量
    x: e.clientX - panel.position.x,
    y: e.clientY - panel.position.y
  }
  
  // 取消吸附状态
  pdfStore.setPanelSnapMode(panelId, 'none') // 设置面板吸附模式为无
  pdfStore.bringPanelToFront(panelId) // 将面板置于顶层
  
  e.preventDefault() // 阻止默认事件
}

// 拖动过程中更新面板位置
function onDrag(e: MouseEvent) { // 鼠标移动时的拖动处理
  if (resizingPanelId.value) { // 如果正在调整大小
    onResize(e) // 调用调整大小函数
    return
  }
  
  if (!draggingPanelId.value) return // 如果没有拖动中的面板，返回
  
  const panel = pdfStore.translationPanels.find(p => p.id === draggingPanelId.value) // 查找拖动中的面板
  if (!panel) return // 如果面板不存在，返回
  
  const newX = e.clientX - dragOffset.value.x // 计算新的X位置
  const newY = e.clientY - dragOffset.value.y // 计算新的Y位置
  
  // 检测是否接近右边缘（侧边栏吸附）
  const distanceToRight = window.innerWidth - (newX + panel.size.width) // 计算到右边缘的距离
  isNearSidebar.value = distanceToRight < SIDEBAR_SNAP_THRESHOLD // 判断是否接近侧边栏
  
  // 检测是否接近任何段落（段落吸附）
  if (!isNearSidebar.value) { // 如果不接近侧边栏
    const allParagraphs = getAllParagraphRects() // 获取所有段落位置
    let nearestParagraph: { id: string; distance: number; rect: DOMRect } | null = null // 初始化最近段落

    // 使用面板中心点来计算距离
    const panelCenterX = newX + panel.size.width / 2 // 计算面板中心X坐标
    const panelCenterY = newY + panel.size.height / 2 // 计算面板中心Y坐标

    for (const p of allParagraphs) { // 遍历所有段落
      // 计算段落光标的中心点
      const markerCenterX = p.rect.left + p.rect.width / 2 // 段落中心X
      const markerCenterY = p.rect.top + p.rect.height / 2 // 段落中心Y

      // 同时检测面板左上角和面板中心到光标的距离
      const distanceFromCorner = Math.sqrt(Math.pow(newX - markerCenterX, 2) + Math.pow(newY - markerCenterY, 2)) // 从角落到段落的距离
      const distanceFromCenter = Math.sqrt(Math.pow(panelCenterX - markerCenterX, 2) + Math.pow(panelCenterY - markerCenterY, 2)) // 从中心到段落的距离
      const distance = Math.min(distanceFromCorner, distanceFromCenter) // 取最小距离

      if (distance < PARAGRAPH_SNAP_THRESHOLD) { // 如果距离小于阈值
        if (!nearestParagraph || distance < nearestParagraph.distance) { // 如果是最近的段落
          nearestParagraph = { id: p.id, distance, rect: p.rect } // 更新最近段落
        }
      }
    }

    if (nearestParagraph) { // 如果找到最近段落
      isNearSnapTarget.value = true // 设置接近吸附目标
      snapTargetParagraphId.value = nearestParagraph.id // 设置目标段落ID
      const snapPos = calculateParagraphSnapPosition(nearestParagraph.id) // 计算吸附位置
      if (snapPos) { // 如果位置计算成功
        snapTargetRect.value = snapPos // 设置吸附目标矩形
      }
    } else { // 如果没有找到
      isNearSnapTarget.value = false // 重置吸附状态
      snapTargetParagraphId.value = null
      snapTargetRect.value = null
    }
  } else { // 如果接近侧边栏
    isNearSnapTarget.value = false // 重置段落吸附状态
    snapTargetParagraphId.value = null
    snapTargetRect.value = null
  }
  
  // 限制在视口内
  const maxX = window.innerWidth - panel.size.width // 计算最大X位置
  const maxY = window.innerHeight - panel.size.height // 计算最大Y位置
  
  pdfStore.updatePanelPosition(draggingPanelId.value, { // 更新面板位置
    x: Math.max(0, Math.min(maxX, newX)), // 限制在0到maxX之间
    y: Math.max(0, Math.min(maxY, newY)) // 限制在0到maxY之间
  })
}

// 停止拖动并执行吸附逻辑
function stopDrag() { // 鼠标释放时停止拖动
  if (draggingPanelId.value) { // 如果有拖动中的面板
    const panel = pdfStore.translationPanels.find(p => p.id === draggingPanelId.value) // 查找面板
    
    if (panel) { // 如果面板存在
      if (isNearSidebar.value) { // 如果接近侧边栏
        // 吸附到侧边栏
        pdfStore.setPanelSnapMode(draggingPanelId.value, 'sidebar') // 设置吸附模式为侧边栏
      } else if (isNearSnapTarget.value && snapTargetRect.value && snapTargetParagraphId.value) { // 如果接近段落
        // 吸附到段落 - 精确覆盖原文位置
        pdfStore.setPanelSnapMode(draggingPanelId.value, 'paragraph', snapTargetParagraphId.value) // 设置吸附模式为段落
        pdfStore.updatePanelPosition(draggingPanelId.value, { // 更新面板位置到吸附点
          x: snapTargetRect.value.left,
          y: snapTargetRect.value.top
        })
        // 调整宽度匹配段落
        pdfStore.updatePanelSize(draggingPanelId.value, { // 更新面板尺寸
          width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, snapTargetRect.value.width)), // 限制宽度在范围内
          height: panel.size.height // 保持高度不变
        })
      }
    }
  }
  
  draggingPanelId.value = null // 重置拖动面板ID
  isNearSnapTarget.value = false // 重置吸附状态
  isNearSidebar.value = false
  snapTargetRect.value = null
  snapTargetParagraphId.value = null
  resizingPanelId.value = null // 重置调整大小ID
  resizeDirection.value = '' // 重置调整方向
}

// 开始调整指定面板的大小
function startResize(e: MouseEvent, panelId: string, direction: string) { // 鼠标按下调整大小手柄时
  e.stopPropagation() // 阻止事件冒泡
  e.preventDefault() // 阻止默认事件
  
  const panel = pdfStore.translationPanels.find(p => p.id === panelId) // 查找要调整的面板
  if (!panel) return // 如果面板不存在，返回
  
  resizingPanelId.value = panelId // 设置调整大小面板ID
  resizeDirection.value = direction // 设置调整方向
  resizeStart.value = { // 记录开始时的状态
    x: e.clientX,
    y: e.clientY,
    width: panel.size.width,
    height: panel.size.height
  }
  
  pdfStore.bringPanelToFront(panelId) // 将面板置于顶层
}

// 调整大小过程中更新面板尺寸
function onResize(e: MouseEvent) { // 鼠标移动时的调整大小处理
  if (!resizingPanelId.value) return // 如果没有调整中的面板，返回
  
  const panel = pdfStore.translationPanels.find(p => p.id === resizingPanelId.value) // 查找调整中的面板
  if (!panel) return // 如果面板不存在，返回
  
  const deltaX = e.clientX - resizeStart.value.x // 计算X方向的变化量
  const deltaY = e.clientY - resizeStart.value.y // 计算Y方向的变化量
  
  let newWidth = panel.size.width // 初始化新宽度
  let newHeight = panel.size.height // 初始化新高度
  let newX = panel.position.x // 初始化新X位置
  let newY = panel.position.y // 初始化新Y位置
  
  if (resizeDirection.value.includes('e')) { // 如果包含东向调整
    newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, resizeStart.value.width + deltaX)) // 计算新宽度，限制在范围内
  }
  if (resizeDirection.value.includes('w')) { // 如果包含西向调整
    const proposedWidth = resizeStart.value.width - deltaX // 计算提议宽度
    if (proposedWidth >= MIN_WIDTH && proposedWidth <= MAX_WIDTH) { // 如果在范围内
      newWidth = proposedWidth // 设置新宽度
      newX = panel.position.x + deltaX // 更新X位置
    }
  }
  if (resizeDirection.value.includes('s')) { // 如果包含南向调整
    newHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, resizeStart.value.height + deltaY)) // 计算新高度
  }
  if (resizeDirection.value.includes('n')) { // 如果包含北向调整
    const proposedHeight = resizeStart.value.height - deltaY // 计算提议高度
    if (proposedHeight >= MIN_HEIGHT && proposedHeight <= MAX_HEIGHT) { // 如果在范围内
      newHeight = proposedHeight // 设置新高度
      newY = panel.position.y + deltaY // 更新Y位置
    }
  }
  
  pdfStore.updatePanelSize(resizingPanelId.value, { width: newWidth, height: newHeight }) // 更新面板尺寸
  pdfStore.updatePanelPosition(resizingPanelId.value, { x: newX, y: newY }) // 更新面板位置
}

// 关闭指定面板
function closePanel(panelId: string) { // 关闭翻译面板
  pdfStore.closeTranslationPanelById(panelId) // 调用store关闭面板
}

// 重新翻译指定面板的内容
async function retranslate(panel: TranslationPanelInstance) { // 异步重新翻译
  const pdfId = libraryStore.currentDocumentId // 获取当前文档ID
  if (!pdfId || !panel.paragraphId) return // 如果缺少必要信息，返回
  
  pdfStore.setPanelLoading(panel.id, true) // 设置面板加载状态
  
  try {
    const result = await aiApi.translateParagraph(pdfId, panel.paragraphId, true) // 调用API重新翻译
    if (result.success) { // 如果翻译成功
      pdfStore.setTranslation(panel.paragraphId, result.translation) // 更新翻译内容
    }
  } catch (error) {
    console.error('Translation failed:', error) // 记录翻译失败错误
  }
}

// 获取指定面板的翻译内容
async function fetchTranslation(panel: TranslationPanelInstance) { // 异步获取翻译
  const pdfId = libraryStore.currentDocumentId // 获取当前文档ID
  if (!pdfId || !panel.paragraphId || panel.translation) return // 如果条件不满足，返回
  
  pdfStore.setPanelLoading(panel.id, true) // 设置面板加载状态
  
  try {
    const result = await aiApi.translateParagraph(pdfId, panel.paragraphId) // 调用API翻译段落
    if (result.success) { // 如果翻译成功
      pdfStore.setTranslation(panel.paragraphId, result.translation) // 更新翻译内容
    }
  } catch (error) {
    console.error('Translation failed:', error) // 记录翻译失败错误
    pdfStore.setTranslation(panel.paragraphId, '翻译失败，请重试') // 设置错误消息
  }
}

// 监听面板数量变化，自动请求翻译
watch(() => pdfStore.translationPanels.length, () => { // 监听翻译面板数组长度变化
  pdfStore.translationPanels.forEach(panel => { // 遍历所有面板
    if (!panel.translation && panel.isLoading) { // 如果面板没有翻译内容且正在加载
      fetchTranslation(panel) // 获取翻译
    }
  })
}, { immediate: true }) // 立即执行一次

// 监听PDF缩放变化，更新吸附面板位置
watch(() => pdfStore.scale, () => { // 监听PDF缩放因子变化
  // 延迟执行以等待DOM更新
  setTimeout(() => {
    debouncedUpdatePositions() // 防抖更新位置
  }, 100)
})

// 更新所有吸附到段落的面板位置
function updateSnappedPanelPositions() { // 更新所有吸附面板的位置
  pdfStore.translationPanels.forEach(panel => { // 遍历所有面板
    if (panel.snapMode === 'paragraph' && panel.snapTargetParagraphId) { // 如果面板吸附到段落
      const snapPos = calculateParagraphSnapPosition(panel.snapTargetParagraphId) // 计算吸附位置
      if (snapPos) { // 如果位置计算成功
        pdfStore.updatePanelPosition(panel.id, { // 更新面板位置
          x: snapPos.left,
          y: snapPos.top
        })
        // 同时更新宽度以匹配段落
        pdfStore.updatePanelSize(panel.id, { // 更新面板尺寸
          width: Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, snapPos.width)), // 限制宽度
          height: panel.size.height // 保持高度
        })
      }
    }
  })
}

// 防抖的位置更新函数，减少频繁更新
const debouncedUpdatePositions = useDebounceFn(updateSnappedPanelPositions, 16) // 16ms防抖

// 使用 requestAnimationFrame 实现平滑滚动跟随
let scrollRafId: number | null = null // RAF请求ID

function onPdfScroll() { // PDF滚动事件处理
  // 取消之前的 RAF 请求
  if (scrollRafId) { // 如果有之前的RAF请求
    cancelAnimationFrame(scrollRafId) // 取消它
  }
  // 使用 RAF 确保流畅更新
  scrollRafId = requestAnimationFrame(() => { // 请求动画帧
    updateSnappedPanelPositions() // 更新吸附面板位置
    scrollRafId = null // 重置ID
  })
}

// 点击面板时聚焦
function focusPanel(panelId: string) { // 将指定面板置于顶层
  pdfStore.bringPanelToFront(panelId) // 调用store置于顶层
}

// 存储事件监听器引用
let pdfContainerRef: Element | null = null // PDF容器元素引用
let resizeObserver: ResizeObserver | null = null // 调整大小观察器引用

// 绑定滚动监听器（带重试机制）
let bindRetryCount = 0 // 绑定重试计数
const MAX_BIND_RETRIES = 10 // 最大重试次数

function bindScrollListener() { // 绑定PDF滚动监听器
  if (pdfContainerRef) return // 如果已经绑定，返回

  pdfContainerRef = document.querySelector('.pdf-scroll-container') // 查找PDF滚动容器
  if (pdfContainerRef) { // 如果找到容器
    pdfContainerRef.addEventListener('scroll', onPdfScroll, { passive: true }) // 添加滚动监听器

    // 监听容器大小变化
    resizeObserver = new ResizeObserver(() => { // 创建大小观察器
      debouncedUpdatePositions() // 更新位置
    })
    resizeObserver.observe(pdfContainerRef) // 观察容器大小变化
    bindRetryCount = 0 // 重置重试计数
  } else if (bindRetryCount < MAX_BIND_RETRIES) { // 如果没找到且未超过重试次数
    // 容器未找到，延迟重试
    bindRetryCount++ // 增加重试计数
    setTimeout(bindScrollListener, 200) // 200ms后重试
  }
}

// 监听 PDF URL 变化，重新绑定监听器
watch(() => pdfStore.currentPdfUrl, () => { // 监听当前PDF URL变化
  // 先解绑旧的监听器
  if (pdfContainerRef) { // 如果有容器引用
    pdfContainerRef.removeEventListener('scroll', onPdfScroll) // 移除滚动监听器
    if (resizeObserver) { // 如果有观察器
      resizeObserver.disconnect() // 断开观察器
      resizeObserver = null // 重置引用
    }
    pdfContainerRef = null // 重置容器引用
  }
  bindRetryCount = 0 // 重置重试计数
  // PDF 切换时重新绑定
  setTimeout(bindScrollListener, 200) // 延迟绑定
}, { immediate: true }) // 立即执行一次

onMounted(() => { // 组件挂载时
  document.addEventListener('mousemove', onDrag) // 添加全局鼠标移动监听
  document.addEventListener('mouseup', stopDrag) // 添加全局鼠标释放监听

  // 延迟绑定，确保 PDF 容器已渲染
  setTimeout(bindScrollListener, 200) // 延迟200ms绑定滚动监听
})

onBeforeUnmount(() => { // 组件卸载前
  document.removeEventListener('mousemove', onDrag) // 移除鼠标移动监听
  document.removeEventListener('mouseup', stopDrag) // 移除鼠标释放监听

  if (pdfContainerRef) { // 如果有容器引用
    pdfContainerRef.removeEventListener('scroll', onPdfScroll) // 移除滚动监听
    pdfContainerRef = null // 重置引用
  }

  if (resizeObserver) { // 如果有观察器
    resizeObserver.disconnect() // 断开观察器
    resizeObserver = null // 重置引用
  }

  if (scrollRafId) { // 如果有RAF请求
    cancelAnimationFrame(scrollRafId) // 取消请求
    scrollRafId = null // 重置ID
  }
})
</script>

<template>
  <!-- 拖动时显示的吸附提示 -->
  <div
    v-if="draggingPanelId && snapTargetRect && isNearSnapTarget"
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
    v-if="draggingPanelId && isNearSidebar"
    class="sidebar-snap-hint fixed z-[998] pointer-events-none right-0 top-0 bottom-0 w-16"
  >
    <div class="sidebar-hint-text">停靠到侧边栏</div>
  </div>

  <!-- 渲染所有翻译面板（排除已停靠到侧边栏的） -->
  <template v-for="(panel, index) in pdfStore.translationPanels.filter(p => !p.isSidebarDocked)" :key="panel.id">
    <div
      class="translation-panel fixed z-[1000] rounded-lg overflow-hidden select-none"
      :class="{ 
        'is-snapped': panel.snapMode === 'paragraph',
        'is-dragging': draggingPanelId === panel.id
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
      <!-- 头部 - 极简细条拖动区域 -->
      <div 
        class="panel-header flex items-center justify-between px-2 py-1 cursor-move"
        @mousedown="startDrag($event, panel.id)"
      >
        <div class="flex items-center gap-1.5">
          <span class="text-xs font-medium text-gray-600 dark:text-gray-400">译文</span>
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
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
          <!-- 字体减小按钮 -->
          <button
            @click.stop="decreaseFontSize(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="减小字体"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
            </svg>
          </button>
          <!-- 字体增大按钮 -->
          <button
            @click.stop="increaseFontSize(panel.id)"
            class="p-1 hover:bg-gray-200/50 dark:hover:bg-[#3e3e42] rounded transition-colors"
            title="增大字体"
          >
            <svg class="w-3 h-3 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <!-- 重新翻译按钮 -->
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
          <!-- 关闭按钮 -->
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
        <!-- 加载中状态 -->
        <div v-if="panel.isLoading" class="flex flex-col items-center justify-center py-6">
          <div class="loading-spinner mb-2"></div>
          <span class="text-gray-400 dark:text-gray-500 text-xs">翻译中...</span>
        </div>

        <!-- 翻译内容 -->
        <div
          v-else
          class="translation-text text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap"
          :style="{ fontSize: getFontSize(panel.id) + 'px' }"
        >
          {{ panel.translation || '暂无翻译' }}
        </div>
      </div>
      
      <!-- 调整大小的边框（非侧边栏模式） -->
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

/* 夜间模式 - 与Chat面板保持一致的深色背景 */
.dark .translation-panel {
  background: #1e1e1e; /* 与Chat一致的深色背景 */
  border-color: #121726;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* 极简顶栏 - 低饱和度云雾般的灰蓝 */
.panel-header {
  height: 24px;
  background: linear-gradient(to right, #e8eef3, #dfe6ed);
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

/* 夜间模式顶栏 - 与sidebar风格一致 */
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

.translation-panel.is-sidebar-docked {
  border-radius: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.1);
}

.dark .translation-panel.is-sidebar-docked {
  border-left-color: rgba(255, 255, 255, 0.08);
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
  to {
    transform: rotate(360deg);
  }
}

/* 滚动条 */
.panel-content::-webkit-scrollbar {
  width: 4px;
}

.panel-content::-webkit-scrollbar-track {
  background: transparent;
}

.panel-content::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}

.panel-content::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

.dark .panel-content::-webkit-scrollbar-thumb {
  background: #4b5563;
}

.dark .panel-content::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}

/* 调整大小边框 */
.resize-handle {
  position: absolute;
  background: transparent;
}

.resize-w {
  left: 0;
  top: 24px;
  bottom: 6px;
  width: 4px;
  cursor: ew-resize;
}

.resize-e {
  right: 0;
  top: 24px;
  bottom: 6px;
  width: 4px;
  cursor: ew-resize;
}

.resize-s {
  bottom: 0;
  left: 6px;
  right: 6px;
  height: 4px;
  cursor: ns-resize;
}

.resize-sw {
  left: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  cursor: nesw-resize;
}

.resize-se {
  right: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  cursor: nwse-resize;
}

.resize-handle:hover {
  background: rgba(120, 140, 160, 0.1);
}

/* 吸附提示框 */
.snap-hint {
  border: 2px dashed rgba(59, 130, 246, 0.6);
  border-radius: 6px;
  background: rgba(59, 130, 246, 0.1);
  transition: all 0.15s ease;
  animation: snap-pulse 1s ease-in-out infinite;
}

@keyframes snap-pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}

.snap-hint-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

/* 侧边栏吸附提示 */
.sidebar-snap-hint {
  background: linear-gradient(to left, rgba(59, 130, 246, 0.15), transparent);
  border-left: 2px dashed rgba(59, 130, 246, 0.5);
}

.sidebar-hint-text {
  position: absolute;
  top: 50%;
  right: 16px;
  transform: translateY(-50%) rotate(-90deg);
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}
</style>
