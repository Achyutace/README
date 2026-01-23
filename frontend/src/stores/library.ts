import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfDocument, PdfParagraph } from '../types'
import { usePdfStore } from './pdf'
import { pdfApi } from '../api'

export const useLibraryStore = defineStore('library', () => {
  const pdfStore = usePdfStore()
  const documents = ref<PdfDocument[]>([])
  const currentDocumentId = ref<string | null>(null)

  const currentDocument = computed(() =>
    documents.value.find(doc => doc.id === currentDocumentId.value) || null
  )

async function addDocument(file: File): Promise<PdfDocument> {
    try {
      // 使用 api/index.ts 中定义的 upload 方法
      const data = await pdfApi.upload(file)
      
      const doc: PdfDocument = {
        id: data.id, // 获取后端生成的 fileHash 作为 pdfId
        name: data.filename,
        url: URL.createObjectURL(file), // 预览仍然使用本地 Blob
        uploadedAt: new Date(),
        pageCount: data.pageCount
      }
      
      // 避免重复添加 (如果后端返回 isNewUpload: false，也可以做相应处理)
      if (!documents.value.some(d => d.id === doc.id)) {
        documents.value.push(doc)
      } else {
        console.log('Document already exists, switching to it.')
      }
      
      // 保存段落数据到 pdfStore (用于翻译上下文等)
      if (data.paragraphs && data.paragraphs.length > 0) {
        pdfStore.setParagraphs(data.id, data.paragraphs as PdfParagraph[])
      }
      
      // 自动选中上传的文档
      selectDocument(doc.id)
      
      return doc
    } catch (error) {
      console.error('Failed to upload PDF:', error)
      throw error
    }
  }

  function removeDocument(id: string) {
    const index = documents.value.findIndex(doc => doc.id === id)
    if (index !== -1) {
      const doc = documents.value[index]
      if (doc) {
        URL.revokeObjectURL(doc.url)
      }
      documents.value.splice(index, 1)
      if (currentDocumentId.value === id) {
        currentDocumentId.value = documents.value[0]?.id || null
      }
    }
  }

  function selectDocument(id: string) {
    if (documents.value.some(doc => doc.id === id)) {
      currentDocumentId.value = id
    }
  }

  function updateDocumentPageCount(id: string, pageCount: number) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      doc.pageCount = pageCount
    }
  }

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
