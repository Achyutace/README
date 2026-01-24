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
  citations?: any[] 
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

// PDF段落数据类型（对应后端 pdf_service.parse_paragraphs 返回）
export interface PdfParagraph {
  id: string           // 段落ID，格式: pdf_chk_{pdf_id前8位}_{页码}_{块号}
  page: number         // 页码（1-based）
  bbox: {              // 段落在PDF页面中的坐标
    x0: number
    y0: number
    x1: number
    y1: number
    width: number
    height: number
  }
  content: string      // 段落文本内容
  wordCount: number    // 单词数
}

// 翻译面板状态
export interface TranslationPanelState {
  isVisible: boolean
  paragraphId: string
  position: { x: number; y: number }
  translation: string
  isLoading: boolean
  originalText: string
}

// 多窗口翻译面板实例
export interface TranslationPanelInstance {
  id: string                    // 唯一ID
  paragraphId: string           // 关联的段落ID
  position: { x: number; y: number }
  size: { width: number; height: number }
  translation: string
  isLoading: boolean
  originalText: string
  // 吸附相关
  snapMode: 'none' | 'paragraph' | 'sidebar'  // 吸附模式
  snapTargetParagraphId: string | null        // 吸附到的目标段落ID（可与原始paragraphId不同）
  isSidebarDocked: boolean                    // 是否停靠到侧边栏
}
