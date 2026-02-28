/*
----------------------------------------------------------------------
                          上传PDF管理
----------------------------------------------------------------------
*/
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PdfDocument, PdfParagraph } from '../types'
import { usePdfStore } from './pdf'
import { pdfApi, libraryApi, notesApi } from '../api'
import type { Note } from '../api' // also import Note
import { savePdfToCache, getPdfFromCache, removePdfFromCache } from '../utils/pdfCache'
import { broadcastSync, syncChannel } from '../utils/broadcast'
import type { SyncMessage } from '../utils/broadcast'
import { dbPutMany, dbGetAll, dbClear, STORES } from '../utils/db'
import { usePdfProcessing } from '../composables/usePdfProcessing'

const LIBRARY_CURRENT_KEY = 'readme_library_current'

// 定义名为 'library' 的 store，使用组合式 API 返回状态与方法
export const useLibraryStore = defineStore('library', () => {

  // 引用 pdf store，用于保存与 PDF 内容相关的段落数据等
  const pdfStore = usePdfStore()
  const { startPolling, stopPolling, isParsed } = usePdfProcessing()

  // 存放所有已上传或已添加的文档信息（初始为空，启动时从 IndexedDB 水合）
  const documents = ref<PdfDocument[]>([])

  const storedCurrent = localStorage.getItem(LIBRARY_CURRENT_KEY)
  // 当前选中的文献库文档 ID（驱动文件加载，由用户操作选中）
  // 注：与 pdf.ts 中的 currentDocumentId 语义不同——
  //   - library.ts 这里的：「用户选择的」文件，用于触发 Blob 加载和持久化
  //   - pdf.ts 中的：「PDF 渲染器当前展示的」文件，用于高亮和段落定位
  const currentDocumentId = ref<string | null>(storedCurrent || null)

  // 缓存各文档的笔记
  const notesCache = ref<Record<string, Note[]>>({})

  // 是否已完成 IndexedDB 水合
  const isHydrated = ref(false)

  // 从 IndexedDB 水合文献元数据到 Pinia
  async function hydrateFromDB() {
    try {
      const records = await dbGetAll<{ id: string; name: string; pageCount?: number; uploadedAt: string; tags?: string[] }>(STORES.LIBRARY)
      if (records.length > 0) {
        documents.value = records.map(rec => ({
          id: rec.id,
          name: rec.name,
          url: '', // Blob URL 刷新后即失效，后续选中时自动拉取
          uploadedAt: rec.uploadedAt ? new Date(rec.uploadedAt) : new Date(),
          pageCount: rec.pageCount,
          tags: rec.tags || []
        }))
        console.log(`[Library] Hydrated ${records.length} documents from IndexedDB`)
      }
    } catch (error) {
      console.warn('[Library] Failed to hydrate from IndexedDB:', error)
    } finally {
      isHydrated.value = true
    }
  }

  // 将当前 documents 异步写入 IndexedDB
  async function persistToDB() {
    try {
      const toSave = documents.value.map(doc => ({
        id: doc.id,
        name: doc.name,
        pageCount: doc.pageCount,
        uploadedAt: doc.uploadedAt.toISOString(),
        tags: doc.tags || []
      }))
      // 先清空再批量写入，确保删除操作也被同步
      await dbClear(STORES.LIBRARY)
      if (toSave.length > 0) {
        await dbPutMany(STORES.LIBRARY, toSave)
      }
    } catch (error) {
      console.warn('[Library] Failed to persist to IndexedDB:', error)
    }
  }

  // 监听 documents 变更，异步写入 IndexedDB（替代同步 localStorage）
  watch(documents, () => {
    if (isHydrated.value) {
      persistToDB()
    }
  }, { deep: true })

  // 监听并持久化当前选中的文档 ID
  watch(currentDocumentId, (newId) => {
    if (newId) localStorage.setItem(LIBRARY_CURRENT_KEY, newId)
    else localStorage.removeItem(LIBRARY_CURRENT_KEY)
  })

  // 计算属性：当前选中的文档对象（找不到返回 null）
  const currentDocument = computed(() =>
    documents.value.find(doc => doc.id === currentDocumentId.value) || null
  )

  // 计算应用中所有已存在的唯一标签
  const allTags = computed(() => {
    const tags = new Set<string>()
    documents.value.forEach(doc => {
      if (doc.tags) doc.tags.forEach(t => tags.add(t))
    })
    return Array.from(tags).sort()
  })

  // 上传文件并将文档信息加入到 library 中，返回创建的 PdfDocument 对象
  async function addDocument(file: File): Promise<PdfDocument> {
    try {
      // 使用 api/index.ts 中定义的 upload 方法上传文件到后端
      const data = await pdfApi.upload(file)

      const resolvedId = data.pdfId
      if (!resolvedId) {
        throw new Error('Upload successful but no document ID returned from backend')
      }

      const doc: PdfDocument = {
        id: resolvedId,  // 后端生成的 pdf id
        name: file.name || data.filename,    // 保持原始上传的文件名
        url: URL.createObjectURL(file),    // 预览仍然使用本地 Blob（便于即时查看）
        uploadedAt: new Date(),    // 记录上传时间
        pageCount: data.pageCount,    // 总页数
        tags: []
      }

      // 避免重复添加（若后端返回的是已存在的记录，可根据需要处理）
      if (!documents.value.some(d => d.id === doc.id)) {
        documents.value.push(doc)
      } else {
        console.log('Document already exists, switching to it.')
      }

      if (data.paragraphs && data.paragraphs.length > 0) {
        pdfStore.setParagraphs(doc.id, data.paragraphs as PdfParagraph[])
      }

      // 将文件保存到 IndexedDB 缓存中
      await savePdfToCache(doc.id, file)

      // 上传完成后自动选中该文档
      selectDocument(doc.id)

      // 启动后端解析进度轮询
      startPolling(doc.id)

      // 广播到其它标签页
      broadcastSync('RELOAD_LIBRARY')

      return doc
    } catch (error) {
      console.error('Failed to upload PDF:', error)
      throw error
    }
  }

  // 从库中移除指定 id 的文档 (持久化)
  async function removeDocument(id: string) {
    const index = documents.value.findIndex(doc => doc.id === id)
    if (index !== -1) {
      const doc = documents.value[index]
      if (doc && doc.url) {
        URL.revokeObjectURL(doc.url)
      }

      // 先进行本地移除 (乐观 UI)
      documents.value.splice(index, 1)

      if (currentDocumentId.value === id) {
        currentDocumentId.value = documents.value[0]?.id || null
      }

      stopPolling(id)
      removePdfFromCache(id)

      // 调用后端接口移除关联
      try {
        await libraryApi.delete(id)
        broadcastSync('RELOAD_LIBRARY')
      } catch (err) {
        console.error('Failed to delete document from backend:', err)
        // 刷新列表以保证同步
        fetchDocuments()
      }
    }
  }

  // 从后端获取 PDF 文件流并创建 Blob URL
  async function loadDocumentBlob(id: string) {
    const doc = documents.value.find(d => d.id === id)
    if (!doc) return

    try {
      // 尝试从 IndexedDB 获取缓存
      let blob = await getPdfFromCache(id)

      if (!blob) {
        // 如果没有缓存，再从后端拉取
        blob = await pdfApi.getSource(id)

        const header = await blob.slice(0, 5).text()
        if (header !== '%PDF-') {
          throw new Error('获取到的文件不是有效的 PDF 格式。')
        }

        // 拉取成功后保存到缓存中
        await savePdfToCache(id, blob)
      }

      doc.url = URL.createObjectURL(blob)
    } catch (error: any) {
      console.error(`Failed to load source for PDF ${id}:`, error)
      alert(error.message || '加载 PDF 失败')
    }
  }

  // 选中指定文档
  async function selectDocument(id: string) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      currentDocumentId.value = id

      // 如果当前没有 url（例如刷新后），则从后端拉取文件流
      if (!doc.url) {
        await loadDocumentBlob(id)
      }

      // 如果该文档未完成解析，启动轮询
      if (!isParsed(id)) {
        startPolling(id)
      }
    } else {
      console.warn(`Document ${id} not found in library`)
    }
  }

  // 注意：初始化时的 URL 加载已移至 hydrateFromDB().then() 中处理
  // 因为 documents 初始为空，需等 IndexedDB 水合完成后再检查

  // 更新文档的总页数
  function updateDocumentPageCount(id: string, pageCount: number) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      doc.pageCount = pageCount
    } else {
      console.warn(`Cannot update page count: Document ${id} not found`)
    }
  }

  // 从后端获取全量文献列表，刷新缓存
  async function fetchDocuments(force: boolean = false) {
    try {
      const data = await libraryApi.list({ pageSize: 50 })
      if (data && Array.isArray(data.items)) {
        // 将后端返回的格式转换为前端 PdfDocument 格式
        const remoteDocs: PdfDocument[] = data.items.map((item: any) => ({
          id: item.pdfId,
          name: item.title,
          url: '', // 初始化时暂无 Blob URL，点击时加载
          uploadedAt: item.addedAt ? new Date(item.addedAt) : new Date(),
          pageCount: item.totalPages || 0,
          tags: item.tags || []
        }))

        // 后端同步策略:
        // 1. 如果 force 为 true，直接替换全量 (比如切换账号后)
        // 2. 否则只更新或添加，不删除 (SWR 风格)
        if (force) {
          // 释放旧的 Blob URL 防泄漏
          documents.value.forEach(doc => {
            if (doc.url) URL.revokeObjectURL(doc.url)
          })
          documents.value = remoteDocs
        } else {
          // 增量同步策略:
          // 1. 更新或添加来自服务器的文档
          remoteDocs.forEach(rd => {
            const idx = documents.value.findIndex(d => d.id === rd.id)
            if (idx !== -1) {
              const doc = documents.value[idx]
              if (doc) {
                doc.name = rd.name
                doc.pageCount = rd.pageCount
                doc.tags = rd.tags
              }
            } else {
              documents.value.push(rd)
            }
          })
          // 2. 移除本地存在但服务器上已不存在的文档
          const remoteIds = new Set(remoteDocs.map(rd => rd.id))
          documents.value = documents.value.filter(doc => {
            const exists = remoteIds.has(doc.id)
            if (!exists && doc.url) {
              URL.revokeObjectURL(doc.url)
            }
            return exists
          })
        }
      }
    } catch (error) {
      console.error('Failed to sync library docs from backend:', error)
    }
  }

  // 清空库缓存 (退出登录时)
  async function clearLibrary() {
    // 释放所有的 Blob URL
    documents.value.forEach(doc => {
      if (doc.url) URL.revokeObjectURL(doc.url)
      stopPolling(doc.id)
    })

    documents.value = []
    notesCache.value = {}
    currentDocumentId.value = null
    localStorage.removeItem(LIBRARY_CURRENT_KEY)
    // 同时清空 IndexedDB 中的 library store
    await dbClear(STORES.LIBRARY)
  }

  // 初始化时先从 IndexedDB 水合，再从后端增量同步
  hydrateFromDB().then(async () => {
    // 水合完成后，如果有当前选中文档且缺少 URL，则加载 Blob
    if (currentDocumentId.value) {
      const initDoc = documents.value.find(d => d.id === currentDocumentId.value)
      if (initDoc) {
        if (!initDoc.url) {
          await loadDocumentBlob(currentDocumentId.value)
        }
        // 关键：同步 pdfStore，使 activeReaderId 与 currentPdfUrl 都被设置
        // 否则刷新后 paragraphs computed 永远返回 []，翻译图标无法渲染
        const { usePdfStore } = await import('./pdf')
        const pdfStore = usePdfStore()
        if (initDoc.url) {
          pdfStore.setCurrentPdf(initDoc.url, initDoc.id)
          // 若该文档尚未完成解析，启动轮询
          if (!isParsed(initDoc.id)) {
            startPolling(initDoc.id)
          }
        }
      }
    }
    // 从后端增量同步
    fetchDocuments()
  })

  // 监听跨标签页同步
  syncChannel.addEventListener('message', (event: MessageEvent<SyncMessage>) => {
    if (event.data.type === 'RELOAD_LIBRARY') {
      fetchDocuments() // 只静默增量更新，不强制 force
    }
  })

  // -------------------------
  // 标签管理 Action
  // -------------------------

  async function addTagToDocument(pdfId: string, tag: string) {
    if (!tag.trim()) return false
    const trimmedTag = tag.trim()
    const doc = documents.value.find(d => d.id === pdfId)
    if (!doc) return false

    // 乐观更新
    if (!doc.tags) doc.tags = []
    if (!doc.tags.includes(trimmedTag)) {
      doc.tags.push(trimmedTag)
    }

    try {
      const result = await libraryApi.addTag(pdfId, trimmedTag)
      if (!result.success) {
        // 请求失败，回滚
        doc.tags = doc.tags.filter(t => t !== trimmedTag)
        console.error('Failed to add tag:', result.error)
        return false
      }
      return true
    } catch (err) {
      doc.tags = doc.tags.filter(t => t !== trimmedTag)
      console.error('API Error adding tag:', err)
      return false
    }
  }

  async function removeTagFromDocument(pdfId: string, tag: string) {
    const doc = documents.value.find(d => d.id === pdfId)
    if (!doc || !doc.tags || !doc.tags.includes(tag)) return false

    // 乐观更新
    doc.tags = doc.tags.filter(t => t !== tag)

    try {
      const result = await libraryApi.removeTag(pdfId, tag)
      if (!result.success) {
        // 回滚
        doc.tags.push(tag)
        console.error('Failed to remove tag:', result.error)
        return false
      }
      return true
    } catch (err) {
      doc.tags.push(tag)
      console.error('API Error removing tag:', err)
      return false
    }
  }

  // -------------------------
  // 笔记缓存读取 Action
  // -------------------------
  async function getDocumentNotes(pdfId: string, forceRefresh = false): Promise<Note[]> {
    if (!forceRefresh && notesCache.value[pdfId]) {
      return notesCache.value[pdfId]
    }

    try {
      const response = await notesApi.getNotes(pdfId)
      if (response && response.success) {
        notesCache.value[pdfId] = response.notes || []
        return notesCache.value[pdfId]
      }
      return []
    } catch (err) {
      console.error(`Error fetching notes for ${pdfId}:`, err)
      return []
    }
  }

  // 导出状态与方法供组件使用
  return {
    documents,
    currentDocumentId,
    currentDocument,
    addDocument,
    removeDocument,
    selectDocument,
    updateDocumentPageCount,
    fetchDocuments,
    clearLibrary,
    addTagToDocument,
    removeTagFromDocument,
    getDocumentNotes,
    notesCache,
    allTags
  }
})
