import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage, Roadmap, PdfParagraph } from '../types'
// 当前用户ID，需要添加登陆验证逻辑
// TODO
const CURRENT_USER_ID = 'default_user' 
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

// 请求拦截器，自动注入 X-User-Id 
api.interceptors.request.use((config) => {
  config.headers['X-User-Id'] = CURRENT_USER_ID
  return config
}, (error) => {
  return Promise.reject(error)
})

export interface PdfUploadResponse {
  id: string
  filename: string
  pageCount: number
  fileHash: string
  isNewUpload: boolean
  paragraphs?: PdfParagraph[]  // 段落数据
}

export interface ExtractTextResponse {
  text: string
  blocks: Array<{
    text: string
    pageNumber: number
    bbox: [number, number, number, number]
  }>
}

export interface Note {
  id: number
  file_hash: string
  user_id: string
  page_number: number | null
  title: string
  content: string
  note_type: string
  color: string
  position: any | null
  created_time: string
  updated_time: string
}

export interface CreateNoteRequest {
  pdfId: string
  title?: string
  content: string
  pageNumber?: number
  noteType?: string
  color?: string
  position?: any
}

export interface UpdateNoteRequest {
  title?: string
  content: string
  color?: string
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
  translateText: async (text: string, pdfId?: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/translate/text', { 
      text,
      pdfId, // 发送 pdfId 以获取上下文
      contextParagraphs: 5 // 获取前5段作为上下文
    })
    return data
  },

  // 翻译段落 -> 对应后端 router/translate.py
  translateParagraph: async (pdfId: string, paragraphId: string, force: boolean = false): Promise<{
    success: boolean
    translation: string
    cached: boolean
    paragraphId: string
  }> => {
    const { data } = await api.post('/translate/paragraph', {
      pdfId,
      paragraphId,
      force
    })
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
      userId: CURRENT_USER_ID
    })
    return data
  },
}

/**
 * 聊天会话管理 API
 * 对应后端 router/chatbox.py 的会话管理接口
 */
export const chatSessionApi = {
  // 创建新会话
  createSession: async (): Promise<{ sessionId: string; title: string; isNew: boolean; messageCount: number }> => {
    const { data } = await api.post('/chatbox/new')
    return data
  },

  // 删除会话
  deleteSession: async (sessionId: string): Promise<{ success: boolean; deletedMessages: number }> => {
    const { data } = await api.delete(`/chatbox/session/${sessionId}`)
    return data
  },

  // 获取会话列表
  listSessions: async (pdfId?: string, limit: number = 50): Promise<{
    success: boolean
    sessions: Array<{
      id: string
      pdfId?: string
      title: string
      createdAt: string
      updatedAt: string
      messageCount: number
    }>
    total: number
  }> => {
    const params: any = { limit }
    if (pdfId) params.pdfId = pdfId
    const { data } = await api.get('/chatbox/sessions', { params })
    return data
  },

  // 获取会话消息
  getSessionMessages: async (sessionId: string): Promise<{
    success: boolean
    sessionId: string
    messages: Array<{
      id: number
      role: string
      content: string
      citations?: any[]
      created_time: string
    }>
    total: number
  }> => {
    const { data } = await api.get(`/chatbox/session/${sessionId}/messages`)
    return data
  },

  // 更新会话标题
  updateSessionTitle: async (sessionId: string, title: string): Promise<{
    success: boolean
    sessionId: string
    title: string
  }> => {
    const { data } = await api.put(`/chatbox/session/${sessionId}/title`, { title })
    return data
  },

  // 发送消息（非流式）
  sendMessage: async (
    sessionId: string,
    message: string,
    pdfId?: string,
    mode: 'agent' | 'simple' = 'agent', 
    model?: string, // 支持自定义模型参数
    apiBase?: string,
    apiKey?: string
  ): Promise<{
    sessionId: string
    response: string
    citations?: any[]
  }> => {
    const endpoint = mode === 'simple' 
      ? '/chatbox/simple-chat' 
      : '/chatbox/message'
    const { data } = await api.post(endpoint, {
      sessionId,
      message,
      pdfId,
      userId: CURRENT_USER_ID,
      model, 
      apiBase,
      apiKey
    })
    return data
  },
}

export const notesApi = {
  // 对应后端 router/notes.py
  // 创建笔记
  createNote: async (data: CreateNoteRequest): Promise<{ success: boolean; id: number; message: string }> => {
    const { data: response } = await api.post('/notes', data)
    return response
  },

  // 获取笔记列表
  getNotes: async (pdfId: string, page?: number): Promise<{ success: boolean; notes: Note[]; total: number }> => {
    const params: any = {}
    if (page !== undefined) params.page = page
    const { data } = await api.get(`/notes/${pdfId}`, { params })
    return data
  },

  // 更新笔记
  updateNote: async (noteId: number, data: UpdateNoteRequest): Promise<{ success: boolean; message: string }> => {
    const { data: response } = await api.put(`/notes/${noteId}`, data)
    return response
  },

  // 删除笔记
  deleteNote: async (noteId: number): Promise<{ success: boolean; message: string }> => {
    const { data: response } = await api.delete(`/notes/${noteId}`)
    return response
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