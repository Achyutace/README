# 前端说明文档

## 1. 技术栈

本项目使用以下核心技术和库：

- Vue 3：作为核心前端框架，负责响应式界面构建
- TypeScript：提供静态类型检查，增强代码健壮性
- Vite：作为构建与开发工具，提供快速的热更新体验
- Pinia：全局状态管理库，处理跨组件的数据流
- TailwindCSS：原子化 CSS 框架，负责系统样式
- pdfjs-dist：处理 PDF 文件的阅读、渲染与解析功能
- @tiptap/*：提供富文本编辑器的实现方案
- markdown-it：负责 Markdown 内容的解析与展示
- axios：处理与后端的 HTTP 请求交互

## 2. 缓存架构

### 缓存项分类

- 大文件：PDF 文件 Blob 流及解析数据
- 业务数据：文献库、笔记内容、AI 对话历史、模型列表、系统提示词、API Key 信息
- 配置数据：登录凭证、验证凭据、系统主题设置
- 实时信息：当前选中模型、文档 ID、输入草稿、面板折叠状态

### 存储媒介说明

- IndexedDB：持久化存储，用于大文件及大量结构化数据
- LocalStorage：持久化存储，用于小体积的系统配置
- Pinia Store：运行内存存储，负责全局响应式数据交互
- SessionStorage：内存存储，用于存储会话级别的敏感信息
- 组件状态：管理特定组件生命周期内的临时 UI 状态
- Blob URL Cache：内存映射，用于 PDF 资源的快速访问

### 数据管理策略

| 数据类别 | 典型实体 | 存储媒介 | 读写逻辑 |
| :--- | :--- | :--- | :--- |
| 大文件 | PDF 资源流 | IndexedDB + Blob URL | 优先从本地 IndexedDB 加载，缺失时请求后端并同步更新本地库 |
| 核心业务 | 文献、笔记、聊天记录 | IndexedDB + Pinia | 以 Pinia 为运行时内存中心，变更同步写入 IndexedDB 与后端 |
| 翻译段落 | 翻译结果 | 后端数据库 + Pinia | 以后端缓存为权威，Pinia 仅作会话内临时存储 |
| 安全数据 | PIN 码、API Key | Session/LocalStorage | PIN 码仅存会话，API Key 加密存储 |
| UI 配置 | 主题、面板状态 | LocalStorage + Pinia | 状态变更实时覆盖本地存储以保证持久化 |

## 3. 项目结构

```
frontend/
├── index.html                                 应用入口
├── vite.config.ts                             Vite 配置
├── package.json                               项目依赖
├── tailwind.config.js                         样式配置
├── src/
│   ├── main.ts                                程序启动入口
│   ├── App.vue                                根组件（布局管理）
│   ├── api/                                后端请求接口（模块化拆分）
│   │   ├── index.ts                       入口：子模块聚合导出中心
│   │   ├── client.ts                      核心：Axios 实例与 Token 刷新拦截器
│   │   ├── auth.ts                        认证：登录、注册、用户信息
│   │   ├── pdf.ts                         阅读：上传、解析状态、段落获取
│   │   ├── library.ts                     文献：列表、删除、标签管理
│   │   ├── ai.ts                          智能：摘要、全文/段落翻译、路线图
│   │   ├── chat.ts                        对话：会话管理、消息发送
│   │   └── misc.ts                        其他：笔记、高亮、内部链接
│   ├── stores/                                Pinia 状态中心
│   │   ├── auth.ts                            用户认证、凭证管理
│   │   ├── chat.ts                            对话历史、消息流转
│   │   ├── library.ts                         文献库元数据、文档管理
│   │   ├── pdf.ts                             PDF 核心状态（拆分后仅保留核心渲染数据）
│   │   ├── pdf-ui.ts                          PDF UI 状态（解耦：悬浮窗、弹窗）
│   │   ├── pdf-translation.ts                 PDF 翻译引擎（解耦：流水线预翻译逻辑）
│   │   ├── translation.ts                     划词/全文翻译内容缓存
│   │   ├── theme.ts                           亮暗模式、主题偏好
│   │   ├── panel.ts                           UI 面板展开/折叠状态
│   │   └── roadmap.ts                         路线图数据交互
│   ├── components/                            业务功能组件
│   │   ├── chat-box/                          对话相关：ChatTab, ChatInputArea, ChatMessageList
│   │   ├── pdf/                               阅读相关：PdfViewer, PdfToolbar, TranslationPanel
│   │   ├── notes/                             笔记相关：NotesPanel, NoteEditor
│   │   ├── sidebar/                           导航相关：LibrarySidebar
│   │   └── roadmap/                           可视化：RoadmapTab
│   ├── composables/                           响应式逻辑提取（Hooks）
│   │   ├── usePdfLoader.ts                    PDF 文件加载
│   │   ├── usePageRender.ts                   页面逐页渲染
│   │   ├── usePdfSelection.ts                 PDF 划词选择
│   │   ├── useDraggableWindow.ts              窗口拖拽
│   │   └── useMarkdownRenderer.ts             Markdown 渲染
│   ├── utils/                                 工具函数
│   │   ├── db.ts                              IndexedDB 数据层封装
│   │   ├── PdfHelper.ts                       PDF 操作辅助
│   │   ├── crypto.ts                          API Key 加解密
│   │   └── broadcast.ts                       跨标签页通信
│   ├── types/                                 TypeScript 定义
│   │   ├── index.ts                           通用业务接口
│   │   └── pdf.ts                             PDF 渲染专用类型
│   ├── layouts/                               布局骨架
│   └── style.css                              全局样式与 Tailwind 指令
```

## 4. 实现具体细节

1. 聊天重试
  - 点击用户/ai聊天消息下方的重试按钮，会触发重新发送
  - 前端会在这个会话窗口中保留被重试的消息，刷新/切换会话窗口后消失
  - 后端会在收到请求后清理该消息之后的所有消息，确保上下文一致
2. 新聊天
  - 懒创建，点击新对话不会实际创建会话，只有发出第一条消息之后才会创建会话
  - 前端不会缓存也不会显示在对话列表中，后端数据库也不会存储
3. 登录与注册
  - 登录成功后，强制刷新文献库缓存，会异步请求阻塞保证跳转主页时文献库数据已就位
  - 注册的新用户必定没有文档，清空可能残留的缓存后直接跳转主页
