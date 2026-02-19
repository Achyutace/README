/*
--------------------------------------------------------------------------------
  前端 API 封装（详细中文注释）

  说明：
  - 本文件封装了与后端的所有 HTTP 调用，分为几个部分：PDF 操作、AI 功能、
    聊天会话管理、笔记（notes）等。前端其它模块通过导入这些对象来进行
    与后端的交互，避免在业务代码中散落请求逻辑。+
  - 所有 API 使用 axios 实例 `api`，在实例上统一设置了 baseURL 与超时时间，
    并通过请求拦截器自动注入 `X-User-Id`（当前用户 ID，生产环境应替换为登录信息）。
--------------------------------------------------------------------------------
*/

import axios from 'axios'
import type { Translation, ChatMessage, Roadmap, PdfParagraph, Highlight, PdfMetadata } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

// 请求拦截器：为所有请求自动注入 X-User-Id 头
// 备注：这里可以统一注入 token、traceId 等通用头信息
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

// -----------------------------
// 类型定义（前端期望的接口返回类型）
// -----------------------------

// PDF 上传返回值
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
  id: string                // 后端生成的 pdf id
  filename: string          // 上传文件名
  pageCount: number         // 页数
  fileHash: string          // 文件 Hash，用于去重/校验
  isNewUpload: boolean      // 是否为新上传（true 表示新文件）
  paragraphs?: PdfParagraph[]  // 可选：若后端直接返回解析出的段落
}

// 提取文本接口返回结构（按块）
export interface ExtractTextResponse {
  text: string
  blocks: Array<{
    text: string
    pageNumber: number
    bbox: [number, number, number, number] // 文本块在页面上的边界框
  }>
}

// 笔记（后端 notes 表结构的前端表示）
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
  keywords: string[]  // 笔记关键词列表
  createdAt: string
  updatedAt: string
}

// 创建笔记请求体（前端调用时使用）
export interface CreateNoteRequest {
  pdfId: string
  title?: string
  content: string
  keywords?: string[]  // 笔记关键词列表
  pageNumber?: number
  noteType?: string
  color?: string
  position?: any
}

// 更新笔记请求体
export interface UpdateNoteRequest {
  title?: string
  content: string
  keywords?: string[]  // 笔记关键词列表
  color?: string
}

// 内部链接数据返回类型
export interface InternalLinkData {
  title: string
  url: string
  snippet: string
  published_date: string
  authors: string[]
  source: string
  valid: number  // 1 表示内容完整，0 表示有缺失项
}

// -----------------------------
// PDF 相关 API
// 对应后端： router/upload.py
// -----------------------------
export const pdfApi = {
  // 上传 PDF 文件，返回 PdfUploadResponse
  upload: async (file: File): Promise<PdfUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    // 向后端发送 multipart/form-data 请求上传 PDF 文件，后端负责解析并返回相关信息
    const { data } = await api.post<PdfUploadResponse>('/pdf/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // 获取 PDF 处理状态
  status: async (pdfId: string, fromPage: number = 1): Promise<{
    status: 'pending' | 'processing' | 'completed' | 'failed'
    currentPage: number
    totalPages: number
    paragraphs: PdfParagraph[]
    error?: string
  }> => {
    const { data } = await api.get(`/pdf/${pdfId}/status`, { params: { from_page: fromPage } })
    return data
  },

  // 获取 PDF 信息
  info: async (pdfId: string): Promise<{
    id: string
    pageCount: number
    metadata: PdfMetadata
  }> => {
    const { data } = await api.get(`/pdf/${pdfId}/info`)
    return data
  },

  // 获取 PDF 段落（替代 extractText）
  getParagraphs: async (pdfId: string, page?: number): Promise<{ paragraphs: PdfParagraph[] }> => {
    const params = page ? { page } : {}
    const { data } = await api.get(`/pdf/${pdfId}/paragraphs`, { params })
    return data
  },

  // 获取 PDF 源文件（Blob）
  getSource: async (pdfId: string): Promise<Blob> => {
    const { data } = await api.get(`/pdf/${pdfId}/source`, { responseType: 'blob' })
    return data
  },
}

// -----------------------------
// 高亮 API
// 对应后端：router/highlight.py
// -----------------------------
export const highlightApi = {
  // 创建高亮
  create: async (data: {
    pdfId: string
    page: number
    rects: Array<{ x: number; y: number; width: number; height: number }>
    pageWidth: number
    pageHeight: number
    text?: string
    color?: string
  }): Promise<{ success: boolean; id: number; rects: any }> => {
    const { data: res } = await api.post('/highlight', data)
    return res
  },

  // 获取高亮
  getAll: async (pdfId: string, page?: number): Promise<{
    success: boolean
    highlights: Highlight[]
    total: number
  }> => {
    const params: any = { pdfId }
    if (page) params.page = page
    const { data } = await api.get('/highlight', { params })
    return data
  },

  // 更新高亮 (颜色)
  update: async (id: number, color: string): Promise<{ success: boolean }> => {
    const { data } = await api.put(`/highlight/${id}`, { color })
    return data
  },

  // 删除高亮
  delete: async (id: number): Promise<{ success: boolean }> => {
    const { data } = await api.delete(`/highlight/${id}`)
    return data
  },
}

// -----------------------------
// AI 功能相关 API（聊天、摘要、翻译、关键词抽取等）
// 对应后端： router/chatbox.py 和 router/translate.py
// -----------------------------
export const aiApi = {
  // 生成学习路线图（roadmap），返回 Roadmap 数据结构
  // 后端接口：POST /chatbox/roadmap
  generateRoadmap: async (pdfId: string): Promise<Roadmap> => {
    // const { data } = await api.post<{ roadmap: Roadmap }>('/chatbox/roadmap', { pdfId })
    // FIXME: 后端目前只有 /api/roadmap/ping，还没有实际实现。这里先用 mock 数据或抛出异常，或者前端处理
    // 暂时保留原调用，但预期会失败或需对应后端修改
    try {
      const { data } = await api.post<{ roadmap: Roadmap }>('/chatbox/roadmap', { pdfId })
      return layoutNodes(data.roadmap)
    } catch (e) {
      console.warn('Roadmap API not ready, returning empty/mock')
      throw e
    }
  },

  // 翻译任意文本
  translateText: async (text: string, pdfId?: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/translate/text', {
      text,
      pdfId,
      contextParagraphs: 3
    })
    return data
  },

  // 获取某页的历史翻译
  translatePage: async (pdfId: string, pageNumber: number): Promise<{
    pdfId: string
    page: number
    translations: Record<string, string> // paragraphId -> translation
  }> => {
    const { data } = await api.get(`/translate/page/${pdfId}/${pageNumber}`)
    return data
  },

  // 翻译指定段落（用于按段翻译并可缓存）
  // 后端接口：POST /translate/paragraph
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

  // 对话（非流式）
  chat: async (
    pdfId: string,
    message: string,
    history: Array<{ role: string; content: string }>
  ): Promise<{ response: string; citations: ChatMessage['citations']; sessionId: string }> => {
    const { data } = await api.post('/chatbox/message', {
      pdfId,
      message,
      history,
    })
    return data
  },

  // 流式对话
  streamChat: async (
    pdfId: string,
    message: string,
    sessionId: string,
    onMessage: (chunk: any) => void,
    onError: (err: any) => void
  ): Promise<void> => {
    const token = getAccessToken()
    await fetch(`${api.defaults.baseURL}/chatbox/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ pdfId, message, sessionId })
    }).then(response => {
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) return

      function read() {
        reader?.read().then(({ done, value }) => {
          if (done) return
          const chunk = decoder.decode(value)
          const lines = chunk.split('\n\n')
          lines.forEach(line => {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6))
                onMessage(data)
              } catch (e) {
                console.error('SSE parse error:', e)
              }
            }
          })
          read()
        }).catch(onError)
      }
      read()
    }).catch(onError)
  }
}

// -----------------------------
// 系统 API
// -----------------------------
export const systemApi = {
  health: async (): Promise<{ status: string; services: any }> => {
    const { data } = await api.get('/health')
    return data
  }
}

// -----------------------------
// 聊天会话管理 API（创建/删除/列出会话、获取消息等）
// 对应后端： router/chatbox.py
// -----------------------------
export const chatSessionApi = {
  // 创建新会话，后端返回 sessionId
  createSession: async (): Promise<{ sessionId: string; title: string; isNew: boolean; messageCount: number }> => {
    const { data } = await api.post('/chatbox/new')
    return data
  },

  // 删除会话
  deleteSession: async (sessionId: string): Promise<{ success: boolean; deletedMessages: number }> => {
    const { data } = await api.delete(`/chatbox/session/${sessionId}`)
    return data
  },

  // 列出会话，支持按 pdfId 过滤和分页（limit）
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

  // 获取指定会话的消息列表（后端按时间返回）
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

  // 更新会话的标题（例如用户为会话自定义标题）
  updateSessionTitle: async (sessionId: string, title: string): Promise<{
    success: boolean
    sessionId: string
    title: string
  }> => {
    const { data } = await api.put(`/chatbox/session/${sessionId}/title`, { title })
    return data
  },

  // 发送消息（非流式），支持多模式：agent 或 simple
  // - mode === 'simple'：使用轻量聊天接口
  // - mode === 'agent'：使用更复杂的代理模式（可能触发工具调用等）
  sendMessage: async (
    sessionId: string,
    message: string,
    pdfId?: string,
    mode: 'agent' | 'simple' = 'agent',
    model?: string, // 可选：覆盖后端默认模型
    apiBase?: string, // 可选：自定义 OpenAI-like 的 base URL
    apiKey?: string // 可选：自定义 API Key（谨慎使用）
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

// -----------------------------
// 内部链接数据 API
// -----------------------------

export const linkApi = {
  // 获取内部链接数据（发送 pdfId 和 paragraphId，返回论文信息）
  getLinkData: async (pdfId: string, targetParagraphId: string): Promise<InternalLinkData> => {
    // const defaultData: InternalLinkData = {
    //   title: 'Attention Is All You Need',
    //   url: 'https://arxiv.org/abs/1706.03762',
    //   snippet: '这是一个示例论文的摘要片段，用于展示内部链接数据的结构。',
    //   published_date: '2024-01-01',
    //   authors: ['作者 A', '作者 B'],
    //   source: 'arXiv',
    //   valid: 1
    // }
    const defaultData: InternalLinkData = {
      title: "",
      url: '',
      snippet: '',
      published_date: '',
      authors: [],
      source: '',
      valid: 0
    }
    try {
      const { data } = await api.post<InternalLinkData>('/link/data', {
        pdfId,
        targetParagraphId
      })
      return data || defaultData
    } catch (error) {
      console.warn('Internal link search failed, returning default data', error)
      return defaultData
    }
  }
}

// -----------------------------
// Notes (笔记) API
// 对应后端： router/notes.py
// -----------------------------
export const notesApi = {
  // 创建笔记
  createNote: async (data: CreateNoteRequest): Promise<{ success: boolean; id: number; message: string }> => {
    const { data: response } = await api.post('/notes', data)
    return response
  },

  // 获取某 PDF 的笔记列表，支持分页
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

// -----------------------------
// 辅助函数：为 roadmap 节点生成简单布局
// - 若后端已经返回 position，则保留原样
// - 否则为节点生成网格坐标（列宽250，行高150）
// 备注：生产环境建议使用 dagre/elkjs 等库以获得更优美的布局
// -----------------------------
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
