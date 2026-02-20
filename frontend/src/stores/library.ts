/*
----------------------------------------------------------------------
                          上传PDF管理
----------------------------------------------------------------------
*/
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { PdfDocument, PdfParagraph } from '../types'
import { usePdfStore } from './pdf'
import { pdfApi } from '../api'
import { savePdfToCache, getPdfFromCache, removePdfFromCache } from '../utils/pdfCache'

const LIBRARY_STORAGE_KEY = 'readme_library_docs'
const LIBRARY_CURRENT_KEY = 'readme_library_current'

// 定义名为 'library' 的 store，使用组合式 API 返回状态与方法
export const useLibraryStore = defineStore('library', () => {

  // 引用 pdf store，用于保存与 PDF 内容相关的段落数据等
  const pdfStore = usePdfStore()

  // 初始化时从 localStorage 加载持久化的数据
  const storedDocs = localStorage.getItem(LIBRARY_STORAGE_KEY)
  const initialDocs = storedDocs ? JSON.parse(storedDocs).map((doc: any) => ({
    ...doc,
    url: '', // Object URL 刷新后即失效，因此暂置空，后续选中时会自动拉取源文件流生成新 URL
    uploadedAt: doc.uploadedAt ? new Date(doc.uploadedAt) : new Date()
  })) : []

  // 存放所有已上传或已添加的文档信息
  const documents = ref<PdfDocument[]>(initialDocs)

  const storedCurrent = localStorage.getItem(LIBRARY_CURRENT_KEY)
  // 当前选中的文档 ID，null 表示未选中
  const currentDocumentId = ref<string | null>(storedCurrent || null)

  // 监听并持久化 documents 数组
  watch(documents, (newDocs) => {
    const toSave = newDocs.map(doc => ({
      id: doc.id,
      name: doc.name,
      pageCount: doc.pageCount,
      uploadedAt: doc.uploadedAt.toISOString()
    }))
    localStorage.setItem(LIBRARY_STORAGE_KEY, JSON.stringify(toSave))
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
        pageCount: data.pageCount    // 总页数
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

      return doc
    } catch (error) {
      console.error('Failed to upload PDF:', error)
      throw error
    }
  }

  // 从库中移除指定 id 的文档，释放 Blob URL 并更新当前选中文档
  function removeDocument(id: string) {
    const index = documents.value.findIndex(doc => doc.id === id)
    if (index !== -1) {
      const doc = documents.value[index]
      if (doc) {
        // 释放通过 URL.createObjectURL 创建的临时对象 URL
        URL.revokeObjectURL(doc.url)
      }
      // 从文档列表中移除该文档
      documents.value.splice(index, 1)
      // 如果移除的是当前选中文档，则将当前选中置为第一个文档或 null
      if (currentDocumentId.value === id) {
        currentDocumentId.value = documents.value[0]?.id || null
      }

      // 彻底清理 IndexedDB 中的缓存
      removePdfFromCache(id)
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
    } else {
      console.warn(`Document ${id} not found in library`)
    }
  }

  // 初始化时，如果已有当前选中并且丢失了 URL，则拉取流数据
  if (currentDocumentId.value) {
    const initDoc = documents.value.find(d => d.id === currentDocumentId.value)
    if (initDoc && !initDoc.url) {
      loadDocumentBlob(currentDocumentId.value)
    }
  }

  // 更新文档的总页数
  function updateDocumentPageCount(id: string, pageCount: number) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      doc.pageCount = pageCount
    } else {
      console.warn(`Cannot update page count: Document ${id} not found`)
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
  }
})
