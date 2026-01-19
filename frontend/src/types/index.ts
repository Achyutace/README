export interface PdfDocument {
  id: string
  name: string
  url: string
  uploadedAt: Date
  pageCount?: number
}

export interface TextBlock {
  text: string
  pageNumber: number
  bbox: [number, number, number, number]
  index: number
}

export interface Keyword {
  term: string
  definition?: string
  occurrences: Array<{
    pageNumber: number
    position: [number, number, number, number]
  }>
}

export interface Translation {
  originalText: string
  translatedText: string
  sentences: Array<{
    index: number
    original: string
    translated: string
  }>
}

export interface Summary {
  bullets: string[]
  generatedAt: Date
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  citations?: Array<{
    pageNumber: number
    text: string
  }>
}

export interface AiPanelTab {
  id: 'keywords' | 'summary' | 'translation' | 'chat'
  label: string
  icon: string
}
