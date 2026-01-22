import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfDocument, PdfParagraph } from '../types'
import { usePdfStore } from './pdf'

export const useLibraryStore = defineStore('library', () => {
  const pdfStore = usePdfStore()
  const documents = ref<PdfDocument[]>([])
  const currentDocumentId = ref<string | null>(null)

  const currentDocument = computed(() =>
    documents.value.find(doc => doc.id === currentDocumentId.value) || null
  )

  async function addDocument(file: File): Promise<PdfDocument> {
    // Optimistic UI updates can be tricky with real IDs, so we'll wait for the server
    try {
      // Create FormData
      const formData = new FormData()
      formData.append('file', file)

      // Upload to backend
      const response = await fetch('http://localhost:5000/api/pdf/upload', {
        method: 'POST',
        body: formData,
      })
      
      if (!response.ok) throw new Error('Upload failed')
      
      const data = await response.json()
      
      const doc: PdfDocument = {
        id: data.id, // Use server-generated ID
        name: file.name,
        url: URL.createObjectURL(file), // Still use local URL for viewing
        uploadedAt: new Date(),
        pageCount: data.pageCount
      }
      
      documents.value.push(doc)
      
      // 保存段落数据到 pdfStore
      if (data.paragraphs && data.paragraphs.length > 0) {
        pdfStore.setParagraphs(data.id, data.paragraphs as PdfParagraph[])
      }
      
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
