import axios from 'axios'
import type { Keyword, Summary, Translation, ChatMessage, Roadmap } from '../types'

// 1. 创建 Axios 实例，配置基础设置
const api = axios.create({
  // 优先从环境变量读取 API 地址，否则默认使用本地 5000 端口
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 30000, 
})

/**
 * 响应类型定义
 */
export interface PdfUploadResponse {
  id: string        // PDF 在服务器上的唯一标识
  filename: string  // 文件名
  pageCount: number // 总页数
}

export interface ExtractTextResponse {
  text: string      // 提取出的纯文本
  blocks: Array<{   // 带坐标和页码的文本块（用于高亮或精准定位）
    text: string
    pageNumber: number
    bbox: [number, number, number, number]
  }>
}

/**
 * PDF 相关 API 模块
 */
export const pdfApi = {
  // 上传 PDF 文件
  upload: async (file: File): Promise<PdfUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<PdfUploadResponse>('/pdf/upload', formData, {
      // 必须指定为 multipart/form-data 以支持文件上传
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // 提取 PDF 文本内容
  // pageNumber 是可选参数，如果不传则提取全文件
  extractText: async (pdfId: string, pageNumber?: number): Promise<ExtractTextResponse> => {
    const params = pageNumber ? { page: pageNumber } : {}
    const { data } = await api.get<ExtractTextResponse>(`/pdf/${pdfId}/text`, { params })
    return data
  },
}

/**
 * AI 功能相关 API 模块
 */
export const aiApi = {
  // 提取 PDF 关键词
  extractKeywords: async (pdfId: string): Promise<Keyword[]> => {
    const { data } = await api.post<{ keywords: Keyword[] }>('/ai/keywords', { pdfId })
    return data.keywords
  },

  // 生成学习路线图
  generateRoadmap: async (pdfId: string): Promise<Roadmap> => {
    const { data } = await api.post<{ roadmap: Roadmap }>('/ai/roadmap', { pdfId })
    // 自动布局节点位置
    return layoutNodes(data.roadmap)
  },

  // 生成 PDF 后文摘要
  generateSummary: async (pdfId: string): Promise<Summary> => {
    const { data } = await api.post<Summary>('/ai/summary', { pdfId })
    return data
  },

  // 翻译指定文本
  translateText: async (text: string): Promise<Translation> => {
    const { data } = await api.post<Translation>('/ai/translate', { text })
    return data
  },

  // 与 PDF 进行对话（RAG 模式）
  // pdfId: 关联的文档 ID
  // message: 当前用户输入
  // history: 历史对话记录，用于保持上下文
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
    return data // 返回 AI 的答复内容及引用的原文位置(citations)
  },
}

/**
 * 辅助函数：为 Roadmap 节点自动布局
 * 如果节点已有非零位置，则保留；否则使用简单的网格布局
 */
function layoutNodes(data: Roadmap): Roadmap {
  // 检查是否已有位置信息
  if (data.nodes.some(n => n.position && (n.position.x !== 0 || n.position.y !== 0))) {
    return data
  }

  // 使用简单的网格布局
  const nodes = data.nodes.map((node, index) => ({
    ...node,
    position: { x: (index % 3) * 250, y: Math.floor(index / 3) * 150 },
    data: node.data // 保留节点数据
  }))
  
  return { ...data, nodes }
}

export default api
