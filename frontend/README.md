# 前端代码阅读指南

> 本指南面向完全不懂前端的新手，帮助你系统地理解本项目的前端代码。

> 前端是**定义用户如何与应用交互**的部分，在F12里面可以看到最终 HTML 结构，以及 CSS 样式和 JavaScript 逻辑。

## 📋 项目技术栈概览

本项目使用以下技术：

| 技术 | 说明 | 类比 |
|------|------|------|
| **Vue 3** | 前端框架 | 类似 React、Angular |
| **TypeScript** | 带类型的 JavaScript | JavaScript 的超集 |
| **Vite** | 项目构建工具 | 类似 Webpack、Parcel |
| **Pinia** | 状态管理库 | 类似 Redux、Vuex |
| **TailwindCSS** | CSS 工具库 | 原子化 CSS 框架 |

其他依赖库：
- `pdfjs-dist` - PDF 阅读功能
- `@tiptap/*` - 富文本编辑器
- `markdown-it` - Markdown 解析
- `axios` - HTTP 请求

---

## 🎯 学习路径（推荐顺序）

### 第 1 步：基础三件套（HTML/CSS/JS）

| 知识点 | 需要了解的内容 | 重要性 |
|--------|---------------|--------|
| **HTML** | 标签结构、属性、表单元素 | ⭐⭐⭐ |
| **CSS** | 选择器、盒模型、Flexbox 布局 | ⭐⭐⭐ |
| **JavaScript** | 变量、函数、箭头函数、异步(async/await)、模块导入导出 | ⭐⭐⭐⭐⭐ |

**推荐资源**：[MDN Web Docs](https://developer.mozilla.org/zh-CN/)（Mozilla 官方文档）

### 第 2 步：Vue 3 核心概念

本项目使用 Vue 3，需要理解以下核心概念：

#### 1. 响应式数据 (`ref`, `reactive`)

```javascript
import { ref } from 'vue'

// 用 ref 定义响应式数据
const count = ref(0)

// 修改数据时要用 .value
count.value = 1  // 界面会自动更新为 1
```

#### 2. 计算属性 (`computed`)

```javascript
import { ref, computed } from 'vue'

const notesVisible = ref(true)
const chatVisible = ref(false)

// 基于其他数据自动计算
const sidebarVisible = computed(() => {
  return notesVisible.value || chatVisible.value
})
```

#### 3. 生命周期钩子

```javascript
import { onMounted, onBeforeUnmount } from 'vue'

// 组件挂载时执行（类似页面加载完成）
onMounted(() => {
  console.log('组件已创建')
  // 当键盘事件发生时执行 handleKeyboard 函数
  document.addEventListener('keydown', handleKeyboard)
})

// 组件卸载前执行（清理工作）
onBeforeUnmount(() => {
  console.log('组件即将销毁')
  document.removeEventListener('keydown', handleKeyboard)
})
```

#### 4. 事件处理

```html
<!-- 点击事件 -->
<button @click="handleClick">点击</button>

<!-- 鼠标按下事件 -->
<div @mousedown="startDrag">拖动我</div>
```

### 第 3 步：理解 .vue 文件结构

每个 `.vue` 文件包含三部分：

```vue
<script setup lang="ts">
/**
 * 1. 脚本部分：定义数据、函数、逻辑
 */
import { ref } from 'vue'

const message = ref('Hello')

const handleClick = () => {
  message.value = 'World'
}
</script>

<template>
  <!-- 
    2. 模板部分：定义界面结构
    {{ }} 是插值语法，显示变量值
  -->
  <div class="container">
    <p>{{ message }}</p>
    <button @click="handleClick">点击</button>
  </div>
</template>

<style scoped>
/* 
 * 3. 样式部分：CSS
 * scoped 表示样式只作用于当前组件
 */
.container {
  color: blue;
}
</style>
```

---

### 第 4 步：按"入口 → 核心 → 细节"阅读代码

#### 📁 项目结构

```
frontend/
├── index.html                               ← 应用最外层 HTML，构建 app 应用入口
├── vite.config.ts                           ← Vite 配置：路径别名
├── package.json                             ← 前端依赖
├── tailwind.config.js                       ← TailwindCSS 配置（主题、插件、内容扫描）
├── postcss.config.js                        ← PostCSS 插件配置（Tailwind、Autoprefixer 等）
├── tsconfig.json                            ← TypeScript 编译选项（路径别名、目标等）
├── tsconfig.app.json                        ← TypeScript 应用编译配置
├── tsconfig.node.json                       ← TypeScript Node 环境配置
├── src/
│   ├── main.ts                              ← 程序入口：创建 app 应用，挂载
│   ├── App.vue                              ← 根组件：定义整体布局（三栏结构）与行为
│   ├── style.css                            ← 全局样式：Tailwind 引入、自定义全局 CSS 规则
│   ├── api/                                 ← HTTP 请求封装（例如 axios 实例，统一接口封装）
│   │   └── index.ts                         ← 导出所有后端交互函数（用户、文档、AI 会话等）
│   ├── types/                               ← TypeScript 类型定义（接口、模型、API 返回类型）
│   │   ├── index.ts                         ← 通用类型定义
│   │   └── pdf.ts                           ← PDF 相关类型定义
│   ├── stores/                              ← Pinia 状态管理（全局状态与动作）
│   │   ├── library.ts                       ← 文档库状态：当前库、检索结果、筛选条件
│   │   ├── pdf.ts                           ← PDF 阅读器状态：当前页、缩放、加载进度
│   │   ├── ai.ts                            ← AI 对话状态：会话历史、当前请求、模型设置
│   │   ├── theme.ts                         ← 主题状态：亮/暗模式、主题持久化（localStorage）
│   │   └── translation.ts                   ← 翻译状态：翻译设置、缓存、多段翻译管理
│   ├── composables/                         ← Vue 组合式函数（可复用的响应式逻辑）
│   │   ├── useDraggableWindow.ts            ← 可拖动窗口逻辑
│   │   ├── useResizableWindow.ts            ← 可调整大小窗口逻辑
│   │   ├── usePdfLoader.ts                  ← PDF 加载逻辑
│   │   ├── usePageRender.ts                 ← PDF 页面渲染逻辑
│   │   ├── useZoomAnchor.ts                 ← PDF 缩放锚点逻辑
│   │   ├── usePdfSelection.ts               ← PDF 文本选择逻辑
│   │   ├── useSelectText.ts                 ← 文本选择通用逻辑
│   │   └── useNotesLookup.ts                ← 笔记查找逻辑
│   ├── components/                          ← 可复用 UI 组件（按功能目录划分）
│   │   ├── sidebar/                         ← 左侧导航：库/文件/标签列表与操作
│   │   │   └── LibrarySidebar.vue           ← 列表与筛选、触发打开文档/切换库的事件
│   │   ├── pdf/                             ← PDF 相关组件：渲染、注释、翻译与选中文本工具
│   │   │   ├── PdfViewer.vue                ← PDF 渲染主视图，集成 pdfjs、页面切换与缩放
│   │   │   ├── PdfToolbar.vue               ← PDF 工具栏（缩放、导航、注释、下载）
│   │   │   ├── NotePreviewCard.vue          ← 文档/笔记的缩略预览卡片，用于列表展示
│   │   │   ├── SmartRefCard.vue             ← 智能引用卡片：显示文献引用摘要与跳转
│   │   │   ├── TextSelectionTooltip.vue     ← 文本选中悬浮工具（高亮、注释、翻译）
│   │   │   └── TranslationPanel.vue         ← 多段/对照翻译视图（并列显示原文与译文）
│   │   ├── notes/                           ← 笔记面板：笔记创建、编辑与列表管理
│   │   │   ├── NotesPanel.vue               ← 笔记列表与笔记项操作（新建、删除、搜索）
│   │   │   └── NoteEditor.vue               ← 富文本笔记编辑器（基于 tiptap，支持保存/同步）
│   │   ├── chat-box/                        ← 聊天组件：AI 对话界面与对话相关工具
│   │   │   └── ChatTab.vue                  ← 聊天页签：消息流、输入框、上下文操作按钮
│   │   └── roadmap/                         ← 路线图/思维图视图组件
│   │       └── RoadmapTab.vue               ← 路线图主视图：节点渲染、缩放、拖拽与导出
│   └── utils/                               ← 工具函数（格式化、日期、辅助 DOM 操作等）
│       ├── PdfHelper.ts                     ← PDF 辅助函数
│       └── PdfRender.ts                     ← PDF 渲染工具函数
```

#### 📖 建议阅读顺序

1. **`index.html`** - 最外层 HTML 结构
2. **`src/main.ts`** - 应用如何启动
3. **`src/App.vue`** - 整体布局（三栏结构）
4. **`src/stores/*.ts`** - 理解应用有哪些全局状态
5. **组件文件** - 从简单到复杂逐个阅读

---