import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 30000,
})

export interface PdfUploadResponse {
  id: string
  filename: string
  pageCount: number
}

export interface ExtractTextResponse {
  text: string
  blocks: Array<{
    text: string
    pageNumber: number
    bbox: [number, number, number, number]
  }>
}

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

export const aiApi = {
  extractKeywords: async (pdfId: string): Promise<Keyword[]> => {
    const { data } = await api.post<{ keywords: Keyword[] }>('/ai/keywords', { pdfId })
    return data.keywords
  },

  generateSummary: async (pdfId: string): Promise<Summary> => {
    const { data } = await api.post<Summary>('/ai/summary', { pdfId })
    return data
  },

  translateText: async (text: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/ai/translate', { text })
    return data
  },

  chat: async (
    pdfId: string,
    message: string,
    history: Array<{ role: string; content: string }>
  ): Promise<{ response: string; citations: ChatMessage['citations'] }> => {
    const { data } = await api.post('/ai/chat', {
      pdfId,
      message,
      history,
    })
    return data
  },
}

export default api
