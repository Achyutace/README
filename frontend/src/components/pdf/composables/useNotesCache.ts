/**
 * 笔记缓存 Composable
 * 处理笔记缓存加载、Ctrl+点击查找笔记
 */

import { ref } from 'vue'
import { notesApi, type Note } from '../../../api'
import { getWordAtPoint } from '../utils/pdfHelpers'

export interface NotePreviewData {
  id: number
  title: string
  content: string
}

export interface NotesCacheOptions {
  getCurrentDocumentId?: () => string | null | undefined
  onOpenNotePreview?: (note: NotePreviewData, position: { x: number; y: number }) => void
  onCloseNotePreview?: () => void
}

export function useNotesCache(options: NotesCacheOptions = {}) {
  // 状态
  const notesCache = ref<Note[]>([])
  const isLoadingNotes = ref(false)

  // 加载当前文档的笔记缓存
  async function loadNotesCache(): Promise<void> {
    const docId = options.getCurrentDocumentId?.()
    if (!docId) {
      notesCache.value = []
      return
    }

    isLoadingNotes.value = true
    try {
      const response = await notesApi.getNotes(docId)
      notesCache.value = response.notes || []
    } catch (error) {
      console.error('Failed to load notes for cache:', error)
      notesCache.value = []
    } finally {
      isLoadingNotes.value = false
    }
  }

  // 查找匹配的笔记（模糊匹配标题）
  function findMatchingNote(word: string): Note | null {
    if (!word || word.length < 2) return null

    const wordLower = word.toLowerCase()

    // 精确匹配优先
    for (const note of notesCache.value) {
      if (note.title && note.title.toLowerCase() === wordLower) {
        return note
      }
    }

    // 标题包含该词
    for (const note of notesCache.value) {
      if (note.title && note.title.toLowerCase().includes(wordLower)) {
        return note
      }
    }

    // 该词包含标题（标题较短时）
    for (const note of notesCache.value) {
      if (note.title && note.title.length >= 2 && wordLower.includes(note.title.toLowerCase())) {
        return note
      }
    }

    return null
  }

  // 处理 Ctrl+点击（查找笔记）
  function handleCtrlClick(event: MouseEvent): void {
    if (options.onCloseNotePreview) {
      options.onCloseNotePreview()
    }

    const word = getWordAtPoint(event.clientX, event.clientY)
    if (!word) return

    const matchedNote = findMatchingNote(word)
    if (matchedNote) {
      const cardX = Math.min(event.clientX + 10, window.innerWidth - 340)
      const cardY = Math.min(event.clientY + 10, window.innerHeight - 400)

      if (options.onOpenNotePreview) {
        options.onOpenNotePreview(
          {
            id: matchedNote.id,
            title: matchedNote.title,
            content: matchedNote.content
          },
          { x: Math.max(0, cardX), y: Math.max(0, cardY) }
        )
      }
    }
  }

  // 清理
  function cleanup(): void {
    notesCache.value = []
    isLoadingNotes.value = false
  }

  return {
    notesCache,
    isLoadingNotes,
    loadNotesCache,
    findMatchingNote,
    handleCtrlClick,
    cleanup
  }
}

export type NotesCacheManager = ReturnType<typeof useNotesCache>
