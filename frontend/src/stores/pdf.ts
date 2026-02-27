/*
----------------------------------------------------------------------
                    PDF状态，翻译面板等相关状态管理
----------------------------------------------------------------------
*/
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfParagraph, Highlight, NormalizedRect, HighlightsStorage } from '../types'
import type { PageSize } from '../types/pdf'
import { highlightApi, aiApi, type InternalLinkData } from '../api'

// 实际缩放 150%，显示为 100%
const DEFAULT_SCALE = 1.5

export type { Highlight, NormalizedRect }

export const usePdfStore = defineStore('pdf', () => {
  // ---------------------- 可观察的状态（state） ----------------------
  const currentPdfUrl = ref<string | null>(null) // 当前打开的 PDF 文件 URL
  // PDF 渲染器当前展示的文档 ID（用于高亮隔离、段落定位）
  // 注：与 library.ts 中的 currentDocumentId 语义不同——
  //   - pdf.ts 这里的：渲染器上下文 ID，随 setCurrentPdf 切换
  //   - library.ts 中的：用户在文献库选中的 ID，驱动文件 Blob 加载
  const activeReaderId = ref<string | null>(null) // 当前文档 ID（用于区分不同文档的高亮与段落）
  const currentPage = ref(1) // 当前页码（从 1 开始）
  const totalPages = ref(0) // 文档总页数
  const scale = ref(DEFAULT_SCALE) // 当前缩放比例（内部以 1.5 为基准）
  const isLoading = ref(false) // 文档加载中标志

  // 自动高亮 / 自动翻译 / 图片描述开关
  const autoHighlight = ref(false)
  const autoTranslate = ref(false)
  const imageDescription = ref(false)

  // 文字选择相关信息
  const selectedText = ref<string>('') // 当前被选择的文字内容
  const selectionPosition = ref<{ x: number; y: number } | null>(null) // 选择框在页面上的位置（像素坐标）
  const selectionInfo = ref<{ page: number; rects: NormalizedRect[] } | null>(null) // 详细的选择信息（包含页码与归一化矩形）

  // 所有文档的高亮数据（key: documentId, value: Highlight[]）
  const allHighlights = ref<HighlightsStorage>({})

  // 当前文档的高亮（计算属性，若没有当前文档则返回空数组）
  const highlights = computed(() => {
    if (!activeReaderId.value) return []
    return allHighlights.value[activeReaderId.value] || []
  })

  // 默认高亮颜色（亮黄色）
  const highlightColor = ref('#F6E05E')

  // 当前选中高亮（用于编辑或删除）
  const selectedHighlight = ref<Highlight | null>(null)

  // 是否处于高亮编辑模式
  const isEditingHighlight = ref(false)

  // 所有文档的段落数据（用于翻译/定位等功能）
  const allParagraphs = ref<Record<string, PdfParagraph[]>>({})

  // 页面尺寸数据（用于坐标转换等）
  const pageSizesConstant = ref<PageSize | null>(null)
  const pageSizesArray = ref<PageSize[] | null>(null)

  // 当前文档的段落（计算属性）
  const paragraphs = computed(() => {
    if (!activeReaderId.value) return []
    return allParagraphs.value[activeReaderId.value] || []
  })



  // ---------------------- 全文预翻译状态 ----------------------
  const isPreTranslating = ref(false)
  const preTranslateQueue = ref<string[]>([])
  const preTranslateTotal = ref(0)
  const preTranslateCompleted = ref(0)
  const preTranslatePdfId = ref<string | null>(null)
  const preTranslateProgress = computed(() => {
    if (preTranslateTotal.value === 0) return 0
    return Math.round((preTranslateCompleted.value / preTranslateTotal.value) * 100)
  })

  // UI 显示的缩放百分比
  const scalePercent = computed(() => Math.round((scale.value / DEFAULT_SCALE) * 100))

  // ---------------------- 文档与页面控制 ----------------------
  // 设置当前打开的 PDF（可包含 documentId 用于区分不同文档）
  function setCurrentPdf(url: string, documentId?: string) {
    // 切换文档时清除已有选择和高亮选中状态，避免悬浮 UI 残留
    clearSelection()
    clearHighlightSelection()

    currentPdfUrl.value = url
    activeReaderId.value = documentId || null
    currentPage.value = 1
    scale.value = DEFAULT_SCALE
    isLoading.value = true

    // 确保当前文档在高亮存储中存在对应数组（避免未定义访问）
    if (documentId) {
      if (!allHighlights.value[documentId]) {
        allHighlights.value[documentId] = []
      }
      // 触发初始的后台抓取尝试
      fetchHighlightsForPdf(documentId)
    }
  }

  // 设置文档总页数并结束加载状态
  function setTotalPages(pages: number) {
    totalPages.value = pages
    isLoading.value = false
  }

  // 跳转到指定页（有边界检查）
  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages.value) {
      currentPage.value = page
    } else {
      console.warn(`Invalid page number: ${page}, valid range: 1-${totalPages.value}`)
    }
  }

  function nextPage() {
    goToPage(currentPage.value + 1)
  }

  function prevPage() {
    goToPage(currentPage.value - 1)
  }

  // 缩放控制：逐步放大
  function zoomIn() {
    if (scale.value < 4.5) {
      scale.value = Math.min(4.5, scale.value + 0.1)
    }
  }

  // 缩放控制：逐步缩小
  function zoomOut() {
    if (scale.value > 0.5) {
      scale.value = Math.max(0.5, scale.value - 0.1)
    }
  }

  // 缩放最大最小限制在 0.5（约 33%） 到 4.5（约 300%） 之间
  function setScale(value: number) {
    scale.value = Math.max(0.5, Math.min(4.5, value))
  }

  function setScalePercent(percent: number) {
    const newScale = (percent / 100) * DEFAULT_SCALE
    setScale(newScale)
  }

  // ---------------------- 文本选择与高亮功能 ----------------------
  // 设置被选择的文字和其屏幕位置（用于显示翻译/笔记悬浮框）
  function setSelectedText(text: string, position?: { x: number; y: number }) {
    selectedText.value = text
    selectionPosition.value = position || null
  }

  // 存储选择的详细信息（页码 + 选中字矩形集合）
  function setSelectionInfo(info: { page: number; rects: NormalizedRect[] } | null) {
    selectionInfo.value = info
  }

  // 清空当前选择相关状态
  function clearSelection() {
    selectedText.value = ''
    selectionPosition.value = null
    selectionInfo.value = null
  }

  // 从当前选择创建一个高亮并保存到当前文档
  async function addHighlightFromSelection() {
    // 需要有选择信息、选中文本且存在当前文档 ID
    if (!selectionInfo.value || !selectedText.value || !activeReaderId.value) {
      if (!selectionInfo.value) console.warn('Cannot add highlight: no selection info')
      if (!selectedText.value) console.warn('Cannot add highlight: no selected text')
      if (!activeReaderId.value) console.warn('Cannot add highlight: no document ID')
      return
    }

    const docId = activeReaderId.value
    const page = selectionInfo.value.page
    const pageData = pageSizesArray.value?.[page - 1] || pageSizesConstant.value
    const pageWidth = pageData?.width || 800
    const pageHeight = pageData?.height || 1200

    try {
      const res = await highlightApi.createHighlight({
        pdfId: docId,
        page,
        rects: selectionInfo.value.rects, // contains { left, top, width, height }
        pageWidth,
        pageHeight,
        text: selectedText.value,
        color: highlightColor.value
      })
      if (res.success) {
        // 请求成功后直接从服务端反向刷新，确保本地数据归一化格式及结构对应最新值
        await fetchHighlightsForPdf(docId)

        // 发送广播
        import('../utils/broadcast').then(({ broadcastSync }) => {
          broadcastSync('RELOAD_HIGHLIGHTS', docId)
        })
      }
    } catch (error) {
      console.error('Failed to create highlight remotely', error)
    }
    // 隐藏浮层与预选择
    clearSelection()
  }

  // 获取指定页面的高亮列表
  function getHighlightsByPage(page: number) {
    return highlights.value.filter(h => h.page === page)
  }

  // 设置默认高亮颜色
  function setHighlightColor(color: string) {
    highlightColor.value = color
  }

  // 选中某个高亮（用于展示编辑 / 删除菜单）
  function selectHighlight(highlight: Highlight, position: { x: number; y: number }) {
    selectedHighlight.value = highlight
    isEditingHighlight.value = true
    selectedText.value = highlight.text
    selectionPosition.value = position
  }

  // 清理高亮的选中状态
  function clearHighlightSelection() {
    selectedHighlight.value = null
    isEditingHighlight.value = false
  }

  // 删除当前文档下的某条高亮
  async function removeHighlight(id: string) {
    if (!activeReaderId.value) {
      console.warn('Cannot remove highlight: no current document')
      return
    }

    const docId = activeReaderId.value
    try {
      await highlightApi.deleteHighlight(id)
      // 后台删除成功后同步本地缓存
      if (allHighlights.value[docId]) {
        allHighlights.value[docId] = allHighlights.value[docId].filter(h => String(h.id) !== String(id))
      }

      clearHighlightSelection()
      import('../utils/broadcast').then(({ broadcastSync }) => {
        broadcastSync('RELOAD_HIGHLIGHTS', docId)
      })
    } catch (e) {
      console.error("Failed to delete remote highlight:", e)
    }
  }

  // 更新某条高亮的颜色
  async function updateHighlightColor(id: string, color: string) {
    if (!activeReaderId.value) {
      console.warn('Cannot update highlight color: no current document')
      return
    }

    const docId = activeReaderId.value
    try {
      await highlightApi.updateHighlight(id, color)
      // 更新成功后，改本地样式
      const highlight = allHighlights.value[docId]?.find(h => String(h.id) === String(id))
      if (highlight) {
        highlight.color = color
        import('../utils/broadcast').then(({ broadcastSync }) => {
          broadcastSync('RELOAD_HIGHLIGHTS', docId)
        })
      }
    } catch (e) {
      console.error("Failed to update remote highlight:", e)
    }
  }

  // 判断某个点（x,y）是否落在页面的高亮区域内，并返回相关高亮
  function getHighlightsAtPoint(page: number, x: number, y: number): Highlight[] {
    return highlights.value.filter(h => {
      if (h.page !== page) return false
      return h.rects.some(rect => {
        return x >= rect.left && x <= rect.left + rect.width &&
          y >= rect.top && y <= rect.top + rect.height
      })
    })
  }

  // 删除整个文档对应的高亮数据（例如删除文档或清理数据时使用）
  function removeDocumentHighlights(documentId: string) {
    if (allHighlights.value[documentId]) {
      delete allHighlights.value[documentId]
      import('../utils/broadcast').then(({ broadcastSync }) => {
        broadcastSync('RELOAD_HIGHLIGHTS', documentId)
      })
    }
  }

  // ---------------------- 功能开关 ----------------------
  function toggleAutoHighlight() {
    autoHighlight.value = !autoHighlight.value
  }

  function toggleAutoTranslate() {
    autoTranslate.value = !autoTranslate.value
  }

  function toggleImageDescription() {
    imageDescription.value = !imageDescription.value
  }

  // ---------------------- 段落管理 ----------------------
  // 为某个文档设置段落数据（通常由解析 PDF 得到）
  function setParagraphs(documentId: string, paragraphsData: PdfParagraph[]) {
    allParagraphs.value[documentId] = paragraphsData
  }

  // 增量追加段落（用于后台解析轮询）
  function appendParagraphs(documentId: string, newParagraphs: PdfParagraph[]) {
    if (!newParagraphs.length) return
    const existing = allParagraphs.value[documentId] ?? []
    const existingIds = new Set(existing.map(p => p.id))
    const toAdd = newParagraphs.filter(p => !existingIds.has(p.id))
    if (!toAdd.length) return

    const merged = [...existing, ...toAdd]
    // 确保同一页内的段落按纵坐标正确排序，以防追加错乱
    merged.sort((a, b) => a.page - b.page || (a.bbox?.y0 ?? 0) - (b.bbox?.y0 ?? 0))
    allParagraphs.value[documentId] = merged
  }

  // 获取指定页面对应的段落列表（用于显示翻译、跳转等）
  function getParagraphsByPage(page: number): PdfParagraph[] {
    return paragraphs.value.filter(p => p.page === page)
  }

  // 设置页面尺寸数据
  function setPageSizes(constant: PageSize | null, array: PageSize[] | null) {
    pageSizesConstant.value = constant
    pageSizesArray.value = array
  }

  // ---------------------- 全文预翻译 ----------------------

  // 启动全文预翻译
  async function startPreTranslation(pdfId: string) {
    const docParagraphs = allParagraphs.value[pdfId]
    if (!docParagraphs || docParagraphs.length === 0) return

    isPreTranslating.value = true
    preTranslatePdfId.value = pdfId
    preTranslateQueue.value = docParagraphs.map(p => p.id)
    preTranslateTotal.value = docParagraphs.length
    preTranslateCompleted.value = 0

    await processPreTranslateQueue()
  }

  // 逐个处理预翻译队列
  async function processPreTranslateQueue() {
    // 延迟导入 translation store 避免循环依赖
    const { useTranslationStore } = await import('./translation')
    const translationStore = useTranslationStore()

    while (preTranslateQueue.value.length > 0 && isPreTranslating.value) {
      const paragraphId = preTranslateQueue.value[0] as string

      // 已缓存则跳过
      if (translationStore.translationCache[paragraphId]) {
        preTranslateQueue.value.shift()
        preTranslateCompleted.value++
        continue
      }

      try {
        const pdfId = preTranslatePdfId.value
        if (pdfId) {
          const result = await aiApi.translateParagraph(pdfId, paragraphId)
          if (result.success) {
            translationStore.setTranslation(paragraphId, result.translation)
          }
        }
      } catch (error) {
        console.error(`Pre-translate failed for ${paragraphId}:`, error)
      }

      // 按值移除（防止队列被 prioritize 重排后误删）
      const idx = preTranslateQueue.value.indexOf(paragraphId)
      if (idx !== -1) {
        preTranslateQueue.value.splice(idx, 1)
      }
      preTranslateCompleted.value++
    }

    // 完成
    isPreTranslating.value = false
    preTranslatePdfId.value = null
  }

  // 停止预翻译
  function stopPreTranslation() {
    isPreTranslating.value = false
    preTranslateQueue.value = []
    preTranslatePdfId.value = null
  }

  // 优先翻译指定段落（移到队列最前面）
  function prioritizeParagraph(paragraphId: string) {
    if (!isPreTranslating.value) return
    const index = preTranslateQueue.value.indexOf(paragraphId)
    if (index > 0) {
      preTranslateQueue.value.splice(index, 1)
      preTranslateQueue.value.unshift(paragraphId)
    }
  }

  // ---------------------- 笔记预览卡片（小悬浮卡片） ----------------------
  const notePreviewCard = ref<{
    isVisible: boolean
    note: { id: number | string; title: string; content: string } | null
    position: { x: number; y: number }
  }>({
    isVisible: false,
    note: null,
    position: { x: 0, y: 0 }
  })

  // 打开笔记预览卡片并设置其位置
  function openNotePreviewCard(note: { id: number | string; title: string; content: string }, position: { x: number; y: number }) {
    notePreviewCard.value = {
      isVisible: true,
      note,
      position
    }
  }

  // 关闭并重置笔记预览卡片
  function closeNotePreviewCard() {
    notePreviewCard.value = {
      isVisible: false,
      note: null,
      position: { x: 0, y: 0 }
    }
  }

  // 更新笔记预览卡片位置
  function updateNotePreviewPosition(position: { x: number; y: number }) {
    notePreviewCard.value.position = position
  }

  // ---------------------- 智能引用卡片（如论文引用详情） ----------------------
  const smartRefCard = ref<{
    isVisible: boolean
    isLoading: boolean
    paper: any | null
    position: { x: number; y: number }
    error?: string | null
  }>({
    isVisible: false,
    isLoading: false,
    paper: null,
    position: { x: 0, y: 0 },
    error: null
  })

  function openSmartRefCard(paperData: any, position: { x: number; y: number }) {
    smartRefCard.value = {
      isVisible: true,
      isLoading: false,
      paper: paperData,
      position,
      error: null
    }
  }

  function closeSmartRefCard() {
    smartRefCard.value.isVisible = false
  }

  function updateSmartRefPosition(position: { x: number; y: number }) {
    smartRefCard.value.position = position
  }

  // ---------------------- 内部链接弹窗 ----------------------
  /** PDF 内部链接目标坐标 */
  type DestinationCoords = {
    page: number
    x: number | null
    y: number | null
    zoom: number | null
    type: string
  }

  const internalLinkPopup = ref<{
    isVisible: boolean
    destCoords: DestinationCoords | null
    position: { x: number; y: number }
    linkData: InternalLinkData | null
    paragraphContent: string | null
    isLoading: boolean
    error: string | null
  }>({
    isVisible: false,
    destCoords: null,
    position: { x: 0, y: 0 },
    linkData: null,
    paragraphContent: null,
    isLoading: false,
    error: null
  })

  function openInternalLinkPopup(destCoords: DestinationCoords, position: { x: number; y: number }) {
    internalLinkPopup.value = {
      isVisible: true,
      destCoords,
      position,
      linkData: null,
      paragraphContent: null,
      isLoading: false,
      error: null
    }
  }

  function closeInternalLinkPopup() {
    internalLinkPopup.value.isVisible = false
  }

  function updateInternalLinkPopupPosition(position: { x: number; y: number }) {
    internalLinkPopup.value.position = position
  }

  function setInternalLinkData(data: InternalLinkData | null, paragraphContent?: string, error?: string) {
    internalLinkPopup.value.linkData = data
    internalLinkPopup.value.paragraphContent = paragraphContent || null
    internalLinkPopup.value.error = error || null
  }

  function setInternalLinkLoading(loading: boolean) {
    internalLinkPopup.value.isLoading = loading
  }

  // 从后端批量同步高亮数据
  async function fetchHighlightsForPdf(pdfId: string) {
    try {
      const { success, highlights: hList } = await highlightApi.getHighlights(pdfId)
      if (success && Array.isArray(hList)) {
        // 由于从后端获取的坐标已经是一组包含 {x,y,width,height} 的列表。
        // 而前端预设为 NormalizedRect (left, top, width, height)
        allHighlights.value[pdfId] = hList.map(item => ({
          id: String(item.id),
          page: item.page_number,
          rects: Array.isArray(item.rects)
            ? item.rects.map((r: any) => ({ left: r.x, top: r.y, width: r.width, height: r.height }))
            : [],
          text: item.selected_text || '',
          color: item.color || '#FFFF00'
        }))
      }
    } catch (e) {
      console.error('Failed to reload highlights', e)
    }
  }

  // ---------------------- 跨标签监听 ----------------------
  import('../utils/broadcast').then(({ syncChannel }) => {
    syncChannel.addEventListener('message', (event) => {
      const { type, payload } = event.data
      if (type === 'RELOAD_HIGHLIGHTS') {
        if (payload && payload === activeReaderId.value) {
          fetchHighlightsForPdf(payload)
          console.log(`[Broadcast] Required reloading highlights for PDF: ${payload}`)
        }
      }
    })
  }).catch(e => console.error("Broadcast init failed in PDF store", e))

  // ---------------------- 导出 store 接口 ----------------------
  return {
    currentPdfUrl,
    activeReaderId: activeReaderId,
    currentPage,
    totalPages,
    scale,
    scalePercent,
    isLoading,
    autoHighlight,
    autoTranslate,
    imageDescription,
    selectedText,
    selectionPosition,
    selectionInfo,
    highlights,
    highlightColor,
    selectedHighlight,
    isEditingHighlight,
    setCurrentPdf,
    setTotalPages,
    goToPage,
    nextPage,
    prevPage,
    zoomIn,
    zoomOut,
    setScale,
    setScalePercent,
    setSelectedText,
    setSelectionInfo,
    clearSelection,
    addHighlightFromSelection,
    getHighlightsByPage,
    setHighlightColor,
    selectHighlight,
    clearHighlightSelection,
    removeHighlight,
    updateHighlightColor,
    getHighlightsAtPoint,
    removeDocumentHighlights,
    toggleAutoHighlight,
    toggleAutoTranslate,
    toggleImageDescription,
    // 段落管理
    paragraphs,
    setParagraphs,
    appendParagraphs,
    getParagraphsByPage,
    // 页面尺寸
    pageSizesConstant,
    pageSizesArray,
    setPageSizes,
    // 笔记预览卡片
    notePreviewCard,
    openNotePreviewCard,
    closeNotePreviewCard,
    updateNotePreviewPosition,
    // 智能引用卡片
    smartRefCard,
    openSmartRefCard,
    closeSmartRefCard,
    updateSmartRefPosition,
    // 全文预翻译
    isPreTranslating,
    preTranslateTotal,
    preTranslateCompleted,
    preTranslateProgress,
    startPreTranslation,
    stopPreTranslation,
    prioritizeParagraph,
    // 内部链接弹窗
    internalLinkPopup,
    openInternalLinkPopup,
    closeInternalLinkPopup,
    updateInternalLinkPopupPosition,
    setInternalLinkData,
    setInternalLinkLoading,
  }
})
