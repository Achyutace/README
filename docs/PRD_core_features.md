2. 页面布局 (UI/UX Layout)
页面采用 三栏式布局 (Three-Column Layout)，支持响应式调整。

2.1 左侧边栏 (Navigation Sidebar)
宽度： 固定窄栏（约 200px-250px），可折叠。

功能模块：

Logo 区： 显示应用名称（README）。

文献管理：

文献库 (Library)：列表显示已上传的 PDF。

从文献库移除 (Remove)：删除当前文档。

推荐朋友 (Referral)：营销功能入口。

用户信息 (底部)： 用户头像、昵称、设置入口。

2.2 中间主阅读区 (Main PDF Canvas)
宽度： 自适应占据屏幕剩余空间的 50%-60%。

顶部工具栏 (Top Toolbar)：

缩放控制： 百分比显示、放大 (+)、缩小 (-)。

翻页控制： 当前页/总页数输入框。

功能开关：

自动高亮 (Auto Highlight)：高亮文中重点。

图片说明 (Image Description)：AI 解析图表。

自动翻译 (Auto Translate)：开启/关闭双语对照模式。

PDF 渲染层：

基于 Canvas 或 SVG 渲染 PDF 文件。

支持文本选中（Selection）、复制、划词翻译。

特色功能： 当开启翻译时，在原文段落旁显示悬浮卡片或在右侧对齐显示译文。

2.3 右侧 AI 助手栏 (AI Assistant Panel)
宽度： 约 350px-400px，支持收起/展开。

顶部 Tabs/工具条： 切换不同的 AI 视图（摘要、对话、笔记）。

核心模块（从上到下）：

模块 A：关键词字典 (Keyword Dictionary)：

自动提取文中的专业术语（如 "Chain-of-Thought", "Faithfulness", "Internal Alignment"）。

以 Tag/Chip 形式展示，点击可跳转至文中出现位置或显示定义。

模块 B：三行摘要 (Three-line Summary)：

生成 3 个 bullet points 概括论文核心（核心贡献、不同点、局限性）。

模块 C：全文/段落翻译 (Translation Stream)：

显示当前阅读段落的中文翻译。

关键特性： 句子级索引（如 <1>, <2>），将译文与原文句子对应。

模块 D：AI Chat (Floating/Bottom)：

悬浮在右下角的对话框。

预设 Prompt 气泡：“这篇文章的核心是什么？”、“有什么局限性？”。

输入框：支持用户针对论文内容进行自由提问 (RAG)。

3. 功能详细说明 (Functional Specifications)
3.1 PDF 核心阅读功能
加载与渲染： 必须支持高性能加载大型 PDF（100+页）。

文本交互： 用户鼠标选中文本后，应弹出微型菜单（Tooltip）：

选项：翻译、解释、高亮、复制。

3.2 沉浸式翻译 (Immersive Translation)
逻辑： 不直接覆盖原文。

交互： 点击或滚动到某一段落时，右侧面板（或悬浮层）实时显示该段落的中文译文。

样式： 译文应保持段落结构，并标记句子序号（例如 [1], [2]）以便视线回溯原文。

3.3 RAG (检索增强生成) 问答
索引： 上传 PDF 时，后台需对文本进行切片（Chunking）并向量化。

问答： 用户在右下角提问时，AI 需检索相关段落，并生成基于原文的回答。

引用溯源： 回答中应包含点击跳转链接，点击可定位到 PDF 原文具体位置。