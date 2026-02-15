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
import type { Keyword, Summary, Translation, ChatMessage, Roadmap, PdfParagraph } from '../types'

// TODO: 当前用户ID（占位符），后续需要用真实的登录用户信息替换
const CURRENT_USER_ID = 'default_user'

// 创建 axios 实例并设置基础配置
// - baseURL 可通过环境变量 VITE_API_URL 覆盖
// - timeout 设置为 60s，因为 AI 接口响应可能较慢
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000, // AI 生成可能较慢，增加超时时间
})

// 请求拦截器：为所有请求自动注入 X-User-Id 头
// 备注：这里可以统一注入 token、traceId 等通用头信息
api.interceptors.request.use((config) => {
  config.headers['X-User-Id'] = CURRENT_USER_ID
  return config
}, (error) => {
  return Promise.reject(error)
})

// -----------------------------
// 类型定义（前端期望的接口返回类型）
// -----------------------------

// PDF 上传返回值
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
  created_time: string
  updated_time: string
}

// 创建笔记请求体（前端调用时使用）
export interface CreateNoteRequest {
  pdfId: string
  title?: string
  content: string
  pageNumber?: number
  noteType?: string
  color?: string
  position?: any
}

// 更新笔记请求体
export interface UpdateNoteRequest {
  title?: string
  content: string
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

  // 提取某个 PDF 的文本内容（可按页）
  extractText: async (pdfId: string, pageNumber?: number): Promise<ExtractTextResponse> => {
    const params = pageNumber ? { page: pageNumber } : {}
    const { data } = await api.get<ExtractTextResponse>(`/pdf/${pdfId}/text`, { params })
    return data
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
  // 后端接口：POST /chatbox/roadmap
  generateRoadmap: async (pdfId: string): Promise<Roadmap> => {
    const { data } = await api.post<{ roadmap: Roadmap }>('/chatbox/roadmap', { pdfId })
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
      userId: CURRENT_USER_ID
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
      userId: CURRENT_USER_ID,
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
