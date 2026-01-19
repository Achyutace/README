# Project: Moonlight Clone (Web PDF Reader)

## Core Goal
构建一个专注于学术论文阅读的 Web 应用，核心布局为“左侧导航 + 中间 PDF + 右侧 AI 辅助”。

## Key Features
1. **PDF Canvas**:
   - 基于 `vue-pdf` 渲染。
   - 支持缩放、跳转页码、虚拟滚动 (Virtual Scrolling)。
   - 文本选中后弹出 Tooltip (翻译/解释)。

2. **Split-Pane Layout**:
   - 左侧：文献列表 (Library)。
   - 中间：PDF 阅读区。
   - 右侧：AI 助手 (Panel)，支持 Tab 切换 (关键词/摘要/对话)。

3. **AI Features**:
   - **Immersive Translation**: 在 PDF 右侧或悬浮显示段落对应译文。
   - **Keyword Extraction**: 自动提取术语 (e.g., "Chain-of-Thought") 并显示定义。
   - **Chat**: RAG 风格的问答，引用原文。