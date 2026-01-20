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

export interface RoadmapNodeData {
  label: string
  description: string
  papers: Array<{
    title: string
    link: string
    year?: string
  }>
}

export interface Roadmap {
  nodes: Array<{
    id: string
    type?: string
    data: RoadmapNodeData
    position: { x: number; y: number }
    label?: string // helpful for default node type
  }>
  edges: Array<{
    id: string
    source: string
    target: string
    label?: string
  }>
}

export interface AiPanelTab {
  id: 'roadmap' | 'summary' | 'translation' | 'chat'
  label: string
  icon: string
}
