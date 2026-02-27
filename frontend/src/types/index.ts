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
  translation?: string // 后端返回的已存在译文（若已翻译则携带，否则为 undefined）
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

// 聊天引用来源 
export interface Citation {
  source_type: 'vector' | 'graph'  // 引用类型
  id: string                       // 引用源ID
  text: string                     // 引用文本片段
  score?: number                   // 相似度分数 (可选)
  name?: string                    // 实体名称 (graph 类型专用)
  // 保持兼容性的扩展字段 (如果后端返回了更多信息)
  page?: number                    // 页码 (对 vector 型可能有用)
  url?: string                     // 链接 (对外部源可能有用)
}

// 聊天
export interface ChatMessage {
  id: string    // 消息ID
  role: 'user' | 'assistant'    // 消息角色
  content: string    // 消息内容
  timestamp: Date    // 时间戳
  citations?: Citation[]    // 引用的信息（可选）
  meta?: {
    resendFromIndex?: number  // 从第 N 条消息处重发（用于 UI 分支提示）
    edited?: boolean          // 是否为编辑后重发
  }
}

// 自定义模型配置
export interface CustomModel {
  id: string       // 模型 ID
  name: string     // 模型名称
  apiBase: string  // API 基础 URL
  apiKey: string   // API 密钥
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

// -----------------------------
// Notes (笔记) 相关接口
// -----------------------------

// 笔记对象
export interface Note {
  id: number
  title: string
  content: string
  keywords: string[]
  createdAt: string
  updatedAt: string
}

// 创建笔记请求
export interface CreateNoteRequest {
  pdfId: string
  title?: string
  content: string
  keywords?: string[]
}

// 更新笔记请求
export interface UpdateNoteRequest {
  title?: string
  content?: string
  keywords?: string[]
}

// 笔记操作响应 (创建/更新/删除)
export interface NoteActionResponse {
  success: boolean
  message: string
  id?: number // 仅在创建时返回
}

// 笔记列表响应
export interface NoteListResponse {
  success: boolean
  notes: Note[]
  total: number
}
// 矩形框（左上角坐标 + 宽高）
export interface NormalizedRect {
  left: number
  top: number
  width: number
  height: number
}

// 高亮对象结构
export interface Highlight {
  id: string
  page: number
  rects: NormalizedRect[]
  text: string
  color: string
}

// 存储结构：文档ID -> 高亮列表
export interface HighlightsStorage {
  [documentId: string]: Highlight[]
}
