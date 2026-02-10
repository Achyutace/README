/*
----------------------------------------------------------------------
                            类型定义
----------------------------------------------------------------------
*/ 
// PDF 文档
export interface PdfDocument {
  id: string    // 文档Hash
  name: string    // 文件名
  url: string    // 本地预览URL（Blob URL），不应存储在后端
  uploadedAt: Date    // 上传时间
  pageCount?: number    // 可选的页数属性，后端返回时包含
}

// PDF 段落信息
export interface PdfParagraph {
  id: string   // 段落ID，格式: pdf_chk_{pdf_id前8位}_{页码}_{块号}
  page: number   // 页码（1-based）
  bbox: {   // 段落在PDF页面中的坐标
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

// PDF 文本块
export interface TextBlock {
  text: string    // 文本内容
  pageNumber: number    // 文本所在的页码
  bbox: [number, number, number, number]    // 文本块的坐标
  index: number    // 文本块在PDF中的唯一索引
}

// 关键词
export interface Keyword {
  term: string    // 关键词文本
  definition?: string   // 定义（可选）
  occurrences: Array<{
    pageNumber: number    // 关键词出现的页码
    position: [number, number, number, number]    // 关键词在页面中的坐标
  }>
}

// 翻译
export interface Translation {
  originalText: string    // 原文
  translatedText: string     // 译文
  sentences: Array<{    // 拆分后的句子
    index: number    // 索引
    original: string    // 原文
    translated: string    // 译文
  }>
}

// 摘要
export interface Summary {
  bullets: string[]    // 关键要点列表
  generatedAt: Date    // 时间戳
}

// 聊天
export interface ChatMessage {
  id: string    // 消息ID
  role: 'user' | 'assistant'    // 消息角色
  content: string    // 消息内容
  timestamp: Date    // 时间戳
  citations?: any[]    // 引用的信息（可选）
}

// 路线图
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

// 路线图节点
export interface RoadmapNodeData {
  label: string    // 节点标签
  description: string    // 节点描述
  papers: Array<{
    title: string    // 论文标题
    link: string    // 论文链接
    year?: string    // 发表年份（可选）
  }>
}

// AI 面板的标签页配置
export interface AiPanelTab {
  id: 'roadmap' | 'summary' | 'translation' | 'chat'
  label: string
  icon: string
}

// 翻译面板状态
export interface TranslationPanelState {
  isVisible: boolean   // 是否显示翻译面板
  paragraphId: string    // 关联的段落ID
  position: { x: number; y: number }    // 面板位置
  translation: string    // 翻译结果
  isLoading: boolean    // 是否正在加载翻译结果
  originalText: string    // 原文内容
}

// 翻译面板实例
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
