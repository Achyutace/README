import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PdfDocument } from '../types'

export const useLibraryStore = defineStore('library', () => {
  const documents = ref<PdfDocument[]>([])
  const currentDocumentId = ref<string | null>(null)

  const currentDocument = computed(() =>
    documents.value.find(doc => doc.id === currentDocumentId.value) || null
  )

  function addDocument(file: File): PdfDocument {
    const doc: PdfDocument = {
      id: crypto.randomUUID(),
      name: file.name,
      url: URL.createObjectURL(file),
      uploadedAt: new Date(),
    }
    documents.value.push(doc)
    return doc
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
