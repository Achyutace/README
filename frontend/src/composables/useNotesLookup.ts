/**
 * 笔记查找 Composable
 * 处理 Ctrl+点击快速查找笔记功能
 */

import { ref } from 'vue'
import type { Ref } from 'vue'
import type { Note } from '../api'

export interface UseNotesLookupOptions {
  getNotes: (docId: string) => Promise<{ notes: Note[] }>
  getCurrentDocumentId: () => string | undefined
  onNoteFound?: (note: Note, position: { x: number; y: number }) => void
}

export function useNotesLookup(options: UseNotesLookupOptions) {
  const notesCache = ref<Note[]>([])
  const isLoadingNotes = ref(false)

  /**
   * 加载当前文档的笔记缓存
   */
  async function loadNotesCache(): Promise<void> {
    const docId = options.getCurrentDocumentId?.()
    if (!docId) {
      notesCache.value = []
      return
    }

    isLoadingNotes.value = true
    try {
      const response = await options.getNotes(docId)
      notesCache.value = response.notes || []
    } catch (error) {
      console.error('Failed to load notes for cache:', error)
      notesCache.value = []
    } finally {
      isLoadingNotes.value = false
    }
  }

  /**
   * 清空笔记缓存
   */
  function clearNotesCache(): void {
    notesCache.value = []
  }

  /**
   * 获取点击位置的单词
   */
  function getWordAtPoint(x: number, y: number): string | null {
    let range: Range | null = null

    // Chrome, Edge, Safari
    if (typeof (document as any).caretRangeFromPoint === 'function') {
      range = (document as any).caretRangeFromPoint(x, y)
    }
    // Firefox
    else if (typeof (document as any).caretPositionFromPoint === 'function') {
      const pos = (document as any).caretPositionFromPoint(x, y)
      if (pos?.offsetNode) {
        const newRange = document.createRange()
        newRange.setStart(pos.offsetNode, pos.offset)
        newRange.setEnd(pos.offsetNode, pos.offset)
        range = newRange
      }
    }

    if (!range) return null

    const node = range.startContainer
    if (node.nodeType !== Node.TEXT_NODE) return null

    const text = node.textContent || ''
    const offset = range.startOffset

    let start = offset
    let end = offset

    // 向前找单词开始
    while (start > 0 && /[\w\u4e00-\u9fa5]/.test(text[start - 1] || '')) {
      start--
    }

    // 向后找单词结束
    while (end < text.length && /[\w\u4e00-\u9fa5]/.test(text[end] || '')) {
      end++
    }

    if (start === end) return null

    return text.slice(start, end).trim()
  }

  /**
   * 查找匹配的笔记（模糊匹配标题）
   */
  function findMatchingNote(word: string): Note | null {
    if (!word || word.length < 2) return null

    const wordLower = word.toLowerCase()

    // 精确匹配优先
    for (const note of notesCache.value) {
      if (note.title?.toLowerCase() === wordLower) {
        return note
      }
    }

    // 标题包含该词
    for (const note of notesCache.value) {
      if (note.title?.toLowerCase().includes(wordLower)) {
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

  /**
   * 处理 Ctrl+点击
   */
  function handleCtrlClick(event: MouseEvent): void {
    const word = getWordAtPoint(event.clientX, event.clientY)
    if (!word) return

    const matchedNote = findMatchingNote(word)
    if (matchedNote) {
      const cardX = Math.min(event.clientX + 10, window.innerWidth - 340)
      const cardY = Math.min(event.clientY + 10, window.innerHeight - 400)

      options.onNoteFound?.(matchedNote, {
        x: Math.max(0, cardX),
        y: Math.max(0, cardY)
      })
    }
  }

  return {
    notesCache,
    isLoadingNotes,
    loadNotesCache,
    clearNotesCache,
    getWordAtPoint,
    findMatchingNote,
    handleCtrlClick
  }
}
