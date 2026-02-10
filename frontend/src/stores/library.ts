/*
----------------------------------------------------------------------
                          上传PDF管理
----------------------------------------------------------------------
*/ 
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfDocument, PdfParagraph } from '../types'
import { usePdfStore } from './pdf'
import { pdfApi } from '../api'

// 定义名为 'library' 的 store，使用组合式 API 返回状态与方法
export const useLibraryStore = defineStore('library', () => {

  // 引用 pdf store，用于保存与 PDF 内容相关的段落数据等
  const pdfStore = usePdfStore()

  // 存放所有已上传或已添加的文档信息
  const documents = ref<PdfDocument[]>([])

  // 当前选中的文档 ID，null 表示未选中
  const currentDocumentId = ref<string | null>(null)

  // 计算属性：当前选中的文档对象（找不到返回 null）
  const currentDocument = computed(() =>
    documents.value.find(doc => doc.id === currentDocumentId.value) || null
  )

  // 上传文件并将文档信息加入到 library 中，返回创建的 PdfDocument 对象
  async function addDocument(file: File): Promise<PdfDocument> {
    try {
      // 使用 api/index.ts 中定义的 upload 方法上传文件到后端
      const data = await pdfApi.upload(file)
      
      const doc: PdfDocument = {
        id: data.id,    // 获取后端生成的 fileHash 作为 pdfId
        name: data.filename,    // 文件名
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
      
      // 如果后端返回了段落数据，则保存到 pdfStore 中，供翻译/上下文使用
      if (data.paragraphs && data.paragraphs.length > 0) {
        pdfStore.setParagraphs(data.id, data.paragraphs as PdfParagraph[])
      }
      
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
    }
  }

  // 选中指定文档
  function selectDocument(id: string) {
    if (documents.value.some(doc => doc.id === id)) {
      currentDocumentId.value = id
    }
  }

  // 更新文档的总页数
  function updateDocumentPageCount(id: string, pageCount: number) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      doc.pageCount = pageCount
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
