import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage, Roadmap } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

export interface PdfUploadResponse {
  id: string
  filename: string
  pageCount: number
  fileHash: string
  isNewUpload: boolean
}

export interface ExtractTextResponse {
  text: string
  blocks: Array<{
    text: string
    pageNumber: number
    bbox: [number, number, number, number]
  }>
}

/**
 * PDF 相关 API
 * 对应后端 router/upload.py
 */
export const pdfApi = {
  upload: async (file: File): Promise<PdfUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<PdfUploadResponse>('/pdf/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  extractText: async (pdfId: string, pageNumber?: number): Promise<ExtractTextResponse> => {
    const params = pageNumber ? { page: pageNumber } : {}
    const { data } = await api.get<ExtractTextResponse>(`/pdf/${pdfId}/text`, { params })
    return data
  },
}

/**
 * AI 功能相关 API
 * 对应后端 router/chatbox.py (Chat, Roadmap, Summary) 和 router/translate.py
 */
export const aiApi = {
  // 提取关键词 -> 建议后端加在 router/chatbox.py
  extractKeywords: async (pdfId: string): Promise<Keyword[]> => {
    const { data } = await api.post<{ keywords: Keyword[] }>('/chatbox/keywords', { pdfId })
    return data.keywords
  },

  // 生成学习路线图 -> 建议后端加在 router/chatbox.py
  generateRoadmap: async (pdfId: string): Promise<Roadmap> => {
    const { data } = await api.post<{ roadmap: Roadmap }>('/chatbox/roadmap', { pdfId })
    return layoutNodes(data.roadmap)
  },

  // 生成摘要 -> 建议后端加在 router/chatbox.py
  generateSummary: async (pdfId: string): Promise<Summary> => {
    const { data } = await api.post<Summary>('/chatbox/summary', { pdfId })
    return data
  },

  // 翻译 -> 对应后端 router/translate.py
  // 注意：后端目前是 /translate/paragraph，需要 paragraphId。
  // 如果前端只是想翻译任意文本，后端需要在 router/translate.py 加一个通用接口
  translateText: async (text: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/translate/text', { text })
    return data
  },

  // 对话 -> 对应后端 router/chatbox.py
  chat: async (
    pdfId: string,
    message: string,
    history: Array<{ role: string; content: string }>
  ): Promise<{ response: string; citations: ChatMessage['citations'] }> => {
    // 后端接口是 /chatbox/message
    const { data } = await api.post('/chatbox/message', {
      pdfId,
      message,
      history,
    })
    return data
  },
}

// 辅助布局函数保持不变
function layoutNodes(data: Roadmap): Roadmap {
  if (data.nodes.some(n => n.position && (n.position.x !== 0 || n.position.y !== 0))) {
    return data
  }
  const nodes = data.nodes.map((node, index) => ({
    ...node,
    position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 150 },
    data: node.data
  }))
  return { ...data, nodes }
}

export default api