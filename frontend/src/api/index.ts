import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage, Roadmap, PdfParagraph } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

// ==================== Token 管理 ====================

const TOKEN_KEY = 'readme_access_token'
const REFRESH_TOKEN_KEY = 'readme_refresh_token'
const USER_KEY = 'readme_user'

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function setCurrentUser(user: { id: string; username: string; email: string }) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getCurrentUser(): { id: string; username: string; email: string } | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

export function isAuthenticated(): boolean {
  return !!getAccessToken()
}

// ==================== 请求拦截器：自动注入 Bearer Token ====================

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// ==================== 响应拦截器：自动刷新过期 Token ====================

let isRefreshing = false
let failedQueue: Array<{ resolve: (v: any) => void; reject: (e: any) => void }> = []

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 仅在 401 且非 auth 接口时尝试刷新
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes('/auth/')) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        clearTokens()
        window.dispatchEvent(new CustomEvent('auth:logout'))
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post(
          `${api.defaults.baseURL}/auth/refresh`,
          { refreshToken },
        )
        const newAccessToken = data.accessToken
        localStorage.setItem(TOKEN_KEY, newAccessToken)
        processQueue(null, newAccessToken)
        originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearTokens()
        window.dispatchEvent(new CustomEvent('auth:logout'))
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

/**
 * 认证相关 API
 * 对应后端 route/auth.py
 */
export const authApi = {
  // 注册
  register: async (username: string, email: string, password: string) => {
    const { data } = await api.post('/auth/register', { username, email, password })
    if (data.accessToken) {
      setTokens(data.accessToken, data.refreshToken)
      setCurrentUser(data.user)
    }
    return data
  },

  // 登录
  login: async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password })
    if (data.accessToken) {
      setTokens(data.accessToken, data.refreshToken)
      setCurrentUser(data.user)
    }
    return data
  },

  // 登出
  logout: () => {
    clearTokens()
    window.dispatchEvent(new CustomEvent('auth:logout'))
  },

  // 获取当前用户信息
  getMe: async () => {
    const { data } = await api.get('/auth/me')
    return data.user
  },

  // 刷新 Token
  refreshToken: async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) throw new Error('No refresh token')
    const { data } = await api.post('/auth/refresh', { refreshToken })
    localStorage.setItem(TOKEN_KEY, data.accessToken)
    return data
  },
}

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