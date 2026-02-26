/*
--------------------------------------------------------------------------------
  前端 API 封装（详细中文注释）

  说明：
  - 本文件封装了与后端的所有 HTTP 调用，分为几个部分：PDF 操作、AI 功能、
    聊天会话管理、笔记（notes）等。前端其它模块通过导入这些对象来进行
    与后端的交互，避免在业务代码中散落请求逻辑。+
  - 所有 API 使用 axios 实例 `api`，在实例上统一设置了 baseURL 与超时时间，
    并通过请求拦截器自动注入 `Authorization`（Bearer Token，生产环境应通过登录获取）。
--------------------------------------------------------------------------------
*/

import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage, Roadmap, PdfParagraph, CreateNoteRequest, UpdateNoteRequest, NoteActionResponse, NoteListResponse } from '../types'
export type { Note, CreateNoteRequest, UpdateNoteRequest, NoteActionResponse, NoteListResponse } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

// 请求拦截器：为所有请求自动注入 Authorization 头
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

// ==================== 临时 Mock 认证初始化 ====================
/**
 * 临时解决方案：在没有正式登录界面时，为浏览器预填一个 Mock Token。
 * 
 */
// TODO
// export function initMockAuth() {
//   if (!getAccessToken()) {
//     setTokens('mock-access-token-' + Math.random().toString(36).substring(7), 'mock-refresh-token');
//     setCurrentUser({
//       id: '00000000-0000-0000-0000-000000000000', // 默认 UUID
//       username: 'Guest',
//       email: 'guest@example.com'
//     });
//     console.log('Temporary mock authentication initialized for PDF upload and other APIs.');
//   }
// }

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
  pdfId?: string            // 后端生成的 pdf id
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

  // 提取某个 PDF 的文本内容（可按页）
  extractText: async (pdfId: string, pageNumber?: number): Promise<ExtractTextResponse> => {
    const params = pageNumber ? { page: pageNumber } : {}
    const { data } = await api.get<ExtractTextResponse>(`/pdf/${pdfId}/text`, { params })
    return data
  },

  // 获取 PDF 的原始二进制源文件数据
  getSource: async (pdfId: string): Promise<Blob> => {
    // 设置 responseType 为 blob 确保 axios 原样返回二进制文件
    const response = await api.get(`/pdf/${pdfId}/source`, {
      responseType: 'blob'
    })
    return response.data
  },
}

// -----------------------------
// AI 功能相关 API（聊天、摘要、翻译、关键词抽取等）
// 对应后端： router/chatbox.py 和 router/translate.py
// -----------------------------
export const aiApi = {
  // 提取关键词（返回 Keyword 数组）
  // 后端接口：POST /chatbox/keywords
  extractKeywords: async (pdfId: string): Promise<Keyword[]> => {
    const { data } = await api.post<{ keywords: Keyword[] }>('/chatbox/keywords', { pdfId })
    return data.keywords
  },

  // 生成学习路线图（roadmap），返回 Roadmap 数据结构
  // 后端接口：POST /roadmap
  generateRoadmap: async (pdfId: string): Promise<Roadmap> => {
    const { data } = await api.post<{ roadmap: Roadmap }>('/roadmap', { pdfId })
    // 确保每个节点有 position（便于前端可视化），内部会调用 layoutNodes 做简单布局
    return layoutNodes(data.roadmap)
  },

  // 生成文档摘要
  // 后端接口：POST /chatbox/summary
  generateSummary: async (pdfId: string): Promise<Summary> => {
    const { data } = await api.post<Summary>('/chatbox/summary', { pdfId })
    return data
  },

  // 翻译任意文本（后端应提供通用文本翻译接口）
  // 备注：目前后端实现中还以段落为单位，若需要翻译任意文本需确保后端支持 /translate/text
  translateText: async (text: string, pdfId?: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/translate/text', {
      text,
      pdfId, // 发送 pdfId 以便后端使用上下文（如检索相关段落）
      contextParagraphs: 5 // 建议后端在翻译时考虑前后 5 段作为上下文
    })
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

  // 对话（基于 PDF 的聊天），返回 response 和 citations（引用段落信息）
  // 后端接口：POST /chatbox/message
  chat: async (
    pdfId: string,
    message: string,
    history: Array<{ role: string; content: string }>
  ): Promise<{ response: string; citations: ChatMessage['citations'] }> => {
    const { data } = await api.post('/chatbox/message', {
      pdfId,
      message,
      history,
    })
    return data
  },
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
    pdfId: string,
    mode: 'agent' | 'simple' = 'agent',
    model?: string, // 可选：覆盖后端默认模型
    apiBase?: string, // 可选：自定义 OpenAI-like 的 base URL
    apiKey?: string, // 可选：自定义 API Key（谨慎使用）
    history?: Array<{ role: string; content: string }> // 可选：重发/编辑时传入的历史覆盖
  ): Promise<{
    sessionId: string
    response: string
    citations?: any[]
  }> => {
    const endpoint = mode === 'simple'
      ? '/chatbox/simple-chat'
      : '/chatbox/message'
    const payload: any = {
      sessionId,
      message,
      pdfId,
      model,
      apiBase,
      apiKey
    }
    if (history) {
      payload.history = history
    }
    const { data } = await api.post(endpoint, payload)
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
  createNote: async (data: CreateNoteRequest): Promise<NoteActionResponse> => {
    const { data: response } = await api.post<NoteActionResponse>('/notes', data)
    return response
  },

  // 获取某 PDF 的笔记列表
  getNotes: async (pdfId: string): Promise<NoteListResponse> => {
    const { data } = await api.get<NoteListResponse>(`/notes/${pdfId}`)
    return data
  },

  // 更新笔记
  updateNote: async (noteId: number, data: UpdateNoteRequest): Promise<NoteActionResponse> => {
    const { data: response } = await api.put<NoteActionResponse>(`/notes/${noteId}`, data)
    return response
  },

  // 删除笔记
  deleteNote: async (noteId: number): Promise<NoteActionResponse> => {
    const { data: response } = await api.delete<NoteActionResponse>(`/notes/${noteId}`)
    return response
  },
}

// -----------------------------
// Highlight (高亮) API
// 对应后端： route/highlight.py
// -----------------------------
export const highlightApi = {
  // 创建高亮
  createHighlight: async (data: {
    pdfId: string
    page: number
    rects: Array<{ left: number; top: number; width: number; height: number }>
    pageWidth: number
    pageHeight: number
    text?: string
    color?: string
  }): Promise<{ success: boolean; id: string | number; rects: any[]; message: string }> => {
    // 适配后端接收字典 key："x,y,width,height"
    const payload = {
      ...data,
      rects: data.rects.map(r => ({ x: r.left, y: r.top, width: r.width, height: r.height }))
    }
    const { data: response } = await api.post('/highlight', payload)
    return response
  },

  // 获取高亮
  getHighlights: async (pdfId: string, page?: number): Promise<{ success: boolean; highlights: any[]; total: number }> => {
    const params: any = { pdfId }
    if (page) params.page = page
    const { data } = await api.get('/highlight', { params })
    return data
  },

  // 更新高亮
  updateHighlight: async (highlightId: string | number, color: string): Promise<{ success: boolean }> => {
    const { data } = await api.put(`/highlight/${highlightId}`, { color })
    return data
  },

  // 删除高亮
  deleteHighlight: async (highlightId: string | number): Promise<{ success: boolean }> => {
    const { data } = await api.delete(`/highlight/${highlightId}`)
    return data
  }
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
