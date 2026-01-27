<script setup lang="ts">
// ------------------------- 导入依赖与 store -------------------------
// 引入 Vue 响应式 API、Markdown 支持、代码高亮及应用 store/API
import { ref, nextTick, watch, onMounted, computed, reactive } from 'vue'  // 导入 Vue 的响应式 API 和生命周期钩子
import { useAiStore } from '../../stores/ai'  // 导入 AI 相关的状态管理 store
import { useLibraryStore } from '../../stores/library'  // 导入库相关的状态管理 store
import { usePdfStore } from '../../stores/pdf'  // 导入 PDF 相关的状态管理 store
import { chatSessionApi } from '../../api'  // 导入聊天会话 API

// --- Markdown Imports ---
// 引入 Markdown 渲染库和代码高亮库
import MarkdownIt from 'markdown-it'  // 导入 Markdown 渲染库
import type { Options } from 'markdown-it'  // 导入 MarkdownIt 的选项类型
import hljs from 'highlight.js'  // 导入代码高亮库
import DOMPurify from 'dompurify'  // 导入 HTML 净化库，用于安全渲染
// 引入代码高亮样式
import 'highlight.js/styles/atom-one-dark.css'  // 导入代码高亮样式

// 初始化各个 store 实例
const aiStore = useAiStore()  // 创建 AI store 实例
const libraryStore = useLibraryStore()  // 创建库 store 实例
const pdfStore = usePdfStore()  // 创建 PDF store 实例

// 定义输入消息的响应式变量
const inputMessage = ref('')  // 用户输入的消息内容
// 定义消息容器的引用，用于滚动控制
const messagesContainer = ref<HTMLElement | null>(null)  // 消息列表容器的 DOM 引用

// --- Tooltip State ---
// 控制引用悬浮窗的状态
const tooltipState = reactive({  // 定义 tooltip 的响应式状态
  visible: false,  // 是否显示 tooltip
  x: 0,  // tooltip 的 X 坐标
  y: 0,  // tooltip 的 Y 坐标
  content: null as any // 存储当前的引用数据
})
let tooltipTimeout: any = null  // tooltip 延迟隐藏的定时器

// @ Menu state
// 定义 @ 菜单相关的状态
const showAtMenu = ref(false)  // 是否显示 @ 菜单
const showKeywordSubmenu = ref(false)  // 是否显示关键词子菜单
const selectedReferences = ref<{ type: string; label: string; id: string }[]>([])  // 已选择的引用列表

// Mock keyword indexes
// 模拟的关键词索引数据
const keywordIndexes = [  // 定义关键词索引数组
  { id: 'kw1', label: 'Chain-of-Thought' },  // 关键词项
  { id: 'kw2', label: 'Unlearning' },  // 关键词项
  { id: 'kw3', label: 'Fast-slow-VLA' },  // 关键词项
]

// File attachment state
// 文件附件相关的状态
const fileInput = ref<HTMLInputElement | null>(null)  // 文件输入框的引用
const attachedFiles = ref<{ name: string; id: string }[]>([])  // 已附加的文件列表

// --- Feature: Custom Models & Model State ---
// 自定义模型相关的状态
const showModelMenu = ref(false)  // 是否显示模型菜单
const showCustomModelModal = ref(false) // 自定义模型弹窗
const selectedModel = ref('README Fusion')  // 当前选中的模型

// --- Feature: Chat Mode Toggle ---
// 聊天模式切换
const chatMode = ref<'agent' | 'simple'>('agent')  // 当前聊天模式，agent 或 simple

// 自定义模型数据接口
interface CustomModel {  // 定义自定义模型的接口
  id: string  // 模型 ID
  name: string  // 模型名称
  apiBase: string  // API 基础 URL
  apiKey: string  // API 密钥
}

// 自定义模型列表
const customModels = ref<CustomModel[]>([])  // 存储自定义模型的响应式数组
// 新建自定义模型的临时数据
const newCustomModel = ref({ name: '', apiBase: '', apiKey: '' })  // 新建模型的表单数据

// 计算所有可用模型（用于发送时查找配置）
const allAvailableModels = computed(() => {  // 计算属性，返回所有可用模型
  return [  // 返回默认模型和自定义模型的组合
    { id: 'default', name: 'README Fusion' },  // 默认模型
    ...customModels.value  // 展开自定义模型列表
  ]
})

// --- Feature: Preset Prompts ---
// 预设提示词相关的状态
const showPromptMenu = ref(false)  // 是否显示提示词菜单
const isEditingPrompts = ref(false) // 编辑模式开关
// 默认提示词
const defaultPrompts = [  // 默认的提示词数组
  '这篇文章针对的问题的是什么？',  // 提示词
  '这篇论文有什么创新点？',  // 提示词
  '这篇论文有什么局限性或不足？',  // 提示词
  '这篇论文主要的研究方法是什么？',  // 提示词
  '这篇文章启发了哪些后续的研究？',  // 提示词
]
// 用户提示词（包含默认的）
const userPrompts = ref<{id: string, text: string}[]>(  // 用户提示词的响应式数组
  defaultPrompts.map((p, i) => ({ id: `sys_${i}`, text: p }))  // 将默认提示词转换为对象数组
)

// Chat session state
// 聊天会话相关的状态
const showHistoryPanel = ref(false)  // 是否显示历史面板

// --- Markdown Configuration ---
// 配置 Markdown 渲染器
const md: MarkdownIt = new MarkdownIt({  // 创建 MarkdownIt 实例
  html: false, // 禁用 HTML 标签以防注入,使用 DOMPurify 双重保险
  linkify: true, // 自动识别 URL
  breaks: true, // 换行符转换为 <br>
  highlight: function (str: string, lang: string): string {  // 自定义代码高亮函数
    if (lang && hljs.getLanguage(lang)) {  // 如果语言支持高亮
      try {
        return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${  // 返回高亮后的代码块
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value  // 高亮代码
        }</code></pre>`
      } catch (__) {}  // 忽略错误
    }
    return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${md.utils.escapeHtml(str)}</code></pre>`  // 返回转义的代码块
  }
} as Options)

// 渲染 Markdown 并处理引用标记
const renderMarkdown = (content: string) => {  // 定义渲染 Markdown 的函数
  if (!content) return ''  // 如果内容为空，返回空字符串
  
  // 1. 先进行基础 Markdown 渲染
  let html = md.render(content)  // 渲染 Markdown 为 HTML

  // 2. 正则替换 [n] 为带有特殊 class 和 data-id 的 span
  // 注意：这里使用了简化的正则，避免替换代码块中的内容可能需要更复杂的逻辑，
  // 但对于标准学术回复 [n] 格式通常足够。
  // 替换逻辑：找到 [数字]，替换为 <span class="citation-ref ...">[数字]</span>
  html = html.replace(/\[(\d+)\]/g, (_match, id) => {  // 使用正则替换引用标记
    return `<span class="citation-ref text-primary-600 bg-primary-50 px-1 rounded cursor-pointer font-medium hover:bg-primary-100 transition-colors select-none" data-id="${id}">[${id}]</span>`  // 返回带有样式的 span
  })

  // 3. 净化 HTML，配置允许的标签和属性
  return DOMPurify.sanitize(html, {  // 使用 DOMPurify 净化 HTML
    ADD_TAGS: ['iframe'],  // 允许的额外标签
    ADD_ATTR: ['target', 'data-id', 'class'] // 关键：允许 data-id 和 class 通过净化
  })
}

// --- Interaction Handlers ---

// 处理鼠标在消息内容上的移动（用于显示 Tooltip）
const handleMessageMouseOver = (event: MouseEvent, citations: any[]) => {  // 定义鼠标悬停处理函数
  const target = event.target as HTMLElement  // 获取事件目标元素
  
  // 如果鼠标悬停在引用标签上
  if (target.classList.contains('citation-ref')) {  // 检查是否为引用标签
    const id = parseInt(target.getAttribute('data-id') || '0')  // 获取引用 ID
    const citationData = citations.find(c => c.id === id)  // 查找对应的引用数据
    
    if (citationData) {  // 如果找到引用数据
      if (tooltipTimeout) clearTimeout(tooltipTimeout)  // 清除之前的延迟隐藏定时器
      
      // 计算位置
      const rect = target.getBoundingClientRect()  // 获取目标元素的边界矩形
      // 相对于视口的位置
      tooltipState.x = rect.left + window.scrollX  // 设置 tooltip X 坐标
      tooltipState.y = rect.top + window.scrollY - 10 // 稍微向上偏移
      tooltipState.content = citationData  // 设置 tooltip 内容
      tooltipState.visible = true  // 显示 tooltip
    }
  }
}

const handleMessageMouseOut = (event: MouseEvent) => {  // 定义鼠标移出处理函数
  const target = event.target as HTMLElement  // 获取事件目标元素
  if (target.classList.contains('citation-ref')) {  // 检查是否为引用标签
    // 延迟隐藏，防止鼠标移向 tooltip 时瞬间消失（如果需要交互 tooltip 内容）
    tooltipTimeout = setTimeout(() => {  // 设置延迟隐藏定时器
      tooltipState.visible = false  // 隐藏 tooltip
      tooltipState.content = null  // 清空内容
    }, 300)  // 延迟 300ms
  }
}

// 保持 tooltip 显示（当鼠标移入 tooltip 本身时）
const handleTooltipEnter = () => {  // 定义 tooltip 鼠标进入处理函数
  if (tooltipTimeout) clearTimeout(tooltipTimeout)  // 清除延迟隐藏定时器
}

const handleTooltipLeave = () => {  // 定义 tooltip 鼠标离开处理函数
  tooltipState.visible = false  // 隐藏 tooltip
  tooltipState.content = null  // 清空内容
}

// 处理点击引用（针对外部链接直接跳转）
const handleMessageClick = (event: MouseEvent, citations: any[]) => {  // 定义引用点击处理函数
  const target = event.target as HTMLElement  // 获取事件目标元素
  if (target.classList.contains('citation-ref')) {  // 检查是否为引用标签
    const id = parseInt(target.getAttribute('data-id') || '0')  // 获取引用 ID
    const citationData = citations.find(c => c.id === id)  // 查找对应的引用数据
    
    if (citationData && citationData.source_type === 'external' && citationData.url) {  // 如果是外部链接
      window.open(citationData.url, '_blank')  // 在新标签页打开链接
    }
    // 本地引用点击暂时不做跳转，或者可以滚动到底部列表
  }
}

// Lifecycle
onMounted(() => {  // 组件挂载时的生命周期钩子
  // 从 localStorage 加载自定义模型
  const storedModels = localStorage.getItem('readme_custom_models')  // 获取存储的自定义模型
  if (storedModels) {  // 如果存在存储的数据
    customModels.value = JSON.parse(storedModels)  // 解析并赋值
  }
  
  // TODO: 从后端加载用户预设提示词
  // fetchUserPrompts()
})

// @ Menu handlers
const toggleAtMenu = () => {  // 切换 @ 菜单显示状态
  showAtMenu.value = !showAtMenu.value  // 切换显示状态
  if (!showAtMenu.value) showKeywordSubmenu.value = false  // 如果关闭主菜单，同时关闭子菜单
  closeOtherMenus('at')  // 关闭其他菜单
}

const handleKeywordClick = () => {  // 处理关键词点击
  showKeywordSubmenu.value = !showKeywordSubmenu.value  // 切换子菜单显示状态
}

const selectFrameMode = () => {  // 选择框选模式
  console.log('Frame selection mode activated')  // 记录日志
  closeMenus()  // 关闭所有菜单
}

const selectKeywordIndex = (kw: { id: string; label: string }) => {  // 选择关键词索引
  if (!selectedReferences.value.find(r => r.id === kw.id)) {  // 如果未选择该关键词
    selectedReferences.value.push({ type: 'keyword', label: kw.label, id: kw.id })  // 添加到选择列表
  }
  closeMenus()  // 关闭所有菜单
}

const removeReference = (id: string) => {  // 移除引用
  selectedReferences.value = selectedReferences.value.filter(r => r.id !== id)  // 从列表中过滤掉指定 ID
}

// File handlers
const triggerFileInput = () => {  // 触发文件输入
  fileInput.value?.click()  // 模拟点击文件输入框
}

const handleFileSelect = (event: Event) => {  // 处理文件选择
  const target = event.target as HTMLInputElement  // 获取事件目标
  if (target.files) {  // 如果有选择的文件
    for (const file of target.files) {  // 遍历每个文件
      attachedFiles.value.push({ name: file.name, id: Date.now().toString() + file.name })  // 添加到附件列表
    }
  }
  target.value = ''  // 重置输入框值
}

const removeFile = (id: string) => {  // 移除文件
  attachedFiles.value = attachedFiles.value.filter(f => f.id !== id)  // 从列表中过滤掉指定 ID
}

// --- Prompt Handlers ---
const togglePromptMenu = () => {  // 切换提示词菜单显示状态
  showPromptMenu.value = !showPromptMenu.value  // 切换显示状态
  // Reset edit mode when opening
  if (showPromptMenu.value) isEditingPrompts.value = false  // 打开菜单时重置编辑模式
  closeOtherMenus('prompt')  // 关闭其他菜单
}

const handlePromptClick = (promptText: string) => {  // 处理提示词点击
  // 直接发送
  sendMessage(promptText)  // 发送选中的提示词
  showPromptMenu.value = false  // 关闭菜单
}

const toggleEditPrompts = () => {  // 切换编辑提示词模式
  isEditingPrompts.value = !isEditingPrompts.value  // 切换编辑状态
}

const addNewPrompt = () => {  // 添加新提示词
  userPrompts.value.push({ id: `new_${Date.now()}`, text: '' })  // 添加空提示词项
}

const removePrompt = (index: number) => {  // 移除提示词
  userPrompts.value.splice(index, 1)  // 从数组中移除指定索引的项
}

const savePrompts = async () => {  // 保存提示词
  // 过滤空提示词
  userPrompts.value = userPrompts.value.filter(p => p.text.trim() !== '')  // 过滤掉空提示词
  
  // 模拟发送到后端
  try {
    console.log('Saving prompts to backend for user: default_user', userPrompts.value)  // 记录日志
    // const response = await fetch('/api/user/prompts', { method: 'POST', body: ... })
    isEditingPrompts.value = false  // 退出编辑模式
  } catch (error) {
    console.error('Failed to save prompts', error)  // 记录错误
  }
}

// --- Model Handlers ---
const toggleModelMenu = () => {  // 切换模型菜单显示状态
  showModelMenu.value = !showModelMenu.value  // 切换显示状态
  closeOtherMenus('model')  // 关闭其他菜单
}

const selectModel = (modelName: string) => {  // 选择模型
  selectedModel.value = modelName  // 设置选中的模型
  showModelMenu.value = false  // 关闭菜单
}

// --- Chat Mode Handlers ---
const toggleChatMode = () => {  // 切换聊天模式
  chatMode.value = chatMode.value === 'agent' ? 'simple' : 'agent'  // 在 agent 和 simple 之间切换
  console.log('Chat mode switched to:', chatMode.value)  // 记录日志
}

const openCustomModelModal = () => {  // 打开自定义模型弹窗
  newCustomModel.value = { name: '', apiBase: '', apiKey: '' }  // 重置表单数据
  showCustomModelModal.value = true  // 显示弹窗
  showModelMenu.value = false  // 关闭菜单
}

const saveCustomModel = () => {  // 保存自定义模型
  if (!newCustomModel.value.name || !newCustomModel.value.apiBase) {  // 验证必填字段
    alert('请填写模型名称和 API Base')  // 提示错误
    return
  }
  
  const modelToAdd: CustomModel = {  // 创建新模型对象
    id: `custom_${Date.now()}`,  // 生成唯一 ID
    ...newCustomModel.value  // 展开表单数据
  }
  
  customModels.value.push(modelToAdd)  // 添加到模型列表
  localStorage.setItem('readme_custom_models', JSON.stringify(customModels.value))  // 保存到本地存储
  
  selectedModel.value = modelToAdd.name  // 设置为当前选中模型
  showCustomModelModal.value = false  // 关闭弹窗
}

const deleteCustomModel = (id: string, event: Event) => {  // 删除自定义模型
  event.stopPropagation()  // 阻止事件冒泡
  const modelToDelete = customModels.value.find(m => m.id === id)  // 查找要删除的模型
  if (modelToDelete && confirm('确定删除该自定义模型？')) {  // 确认删除
    customModels.value = customModels.value.filter(m => m.id !== id)  // 从列表中移除
    localStorage.setItem('readme_custom_models', JSON.stringify(customModels.value))  // 更新本地存储
    if (selectedModel.value === modelToDelete.name) {  // 如果删除的是当前选中的模型
      selectedModel.value = 'README Fusion'  // 重置为默认模型
    }
  }
}

// Utility to manage menus
const closeOtherMenus = (active: 'at' | 'model' | 'prompt') => {  // 关闭其他菜单的工具函数
  if (active !== 'at') { showAtMenu.value = false; showKeywordSubmenu.value = false }  // 如果不是 @ 菜单，关闭 @ 菜单
  if (active !== 'model') { showModelMenu.value = false }  // 如果不是模型菜单，关闭模型菜单
  if (active !== 'prompt') { showPromptMenu.value = false }  // 如果不是提示词菜单，关闭提示词菜单
}

const closeMenus = () => {  // 关闭所有菜单
  showAtMenu.value = false  // 关闭 @ 菜单
  showKeywordSubmenu.value = false  // 关闭关键词子菜单
  showModelMenu.value = false  // 关闭模型菜单
  showPromptMenu.value = false  // 关闭提示词菜单
  showHistoryPanel.value = false  // 关闭历史面板
}

// Chat session handlers
const toggleHistoryPanel = () => {  // 切换历史面板显示状态
  showHistoryPanel.value = !showHistoryPanel.value  // 切换显示状态
}

const createNewChat = async () => {  // 创建新聊天
  const pdfId = libraryStore.currentDocument?.id  // 获取当前 PDF ID
  if (pdfId) {  // 如果有 PDF ID
    await aiStore.createNewSession(pdfId)  // 创建新会话
  }
  showHistoryPanel.value = false  // 关闭历史面板
}
const loadChatSession = async (sessionId: string) => {  // 加载聊天会话
  await aiStore.loadSession(sessionId)  // 加载指定会话
  showHistoryPanel.value = false  // 关闭历史面板
}

const deleteChatSession = async (sessionId: string, event: Event) => {  // 删除聊天会话
  event.stopPropagation()  // 阻止事件冒泡
  if (confirm('确定要删除这个对话吗？')) {  // 确认删除
    try {
      await aiStore.deleteSession(sessionId)  // 删除会话
    } catch (error) {
      console.error('删除会话失败:', error)  // 记录错误
    }
  }
}

const getCurrentPdfSessions = () => {  // 获取当前 PDF 的会话列表
  const pdfId = libraryStore.currentDocument?.id  // 获取当前 PDF ID
  if (!pdfId) return []  // 如果没有 PDF ID，返回空数组
  return aiStore.getSessionsByPdfId(pdfId)  // 返回该 PDF 的会话列表
}

const formatTime = (timestamp: string) => {  // 格式化时间显示
  const date = new Date(timestamp)  // 创建日期对象
  const now = new Date()  // 获取当前时间
  const diffMs = now.getTime() - date.getTime()  // 计算时间差（毫秒）
  const diffMins = Math.floor(diffMs / 60000)  // 转换为分钟
  const diffHours = Math.floor(diffMs / 3600000)  // 转换为小时
  const diffDays = Math.floor(diffMs / 86400000)  // 转换为天
  
  if (diffMins < 60) return `${diffMins}分钟前`  // 小于 1 小时
  if (diffHours < 24) return `${diffHours}小时前`  // 小于 1 天
  if (diffDays < 7) return `${diffDays}天前`  // 小于 1 周
  return date.toLocaleDateString('zh-CN')  // 超过 1 周显示日期
}

// --- Send Message Logic (Updated) ---
async function sendMessage(message?: string) {  // 发送消息的主要函数
  const content = message || inputMessage.value.trim()  // 获取消息内容
  if (!content) return  // 如果内容为空，直接返回
  const pdfId = libraryStore.currentDocument?.id  // 获取当前 PDF ID
  if (!pdfId) {  // 如果没有 PDF ID
    console.error('No PDF selected')  // 记录错误
    return
  }
  // 如果没有会话ID，先创建一个
  if (!aiStore.currentSessionId) {  // 如果没有当前会话 ID
    await aiStore.createNewSession(pdfId)  // 创建新会话
  }
  // 乐观更新 UI
  aiStore.addChatMessage({ role: 'user', content })  // 添加用户消息到 UI
  inputMessage.value = ''  // 清空输入框
  aiStore.isLoadingChat = true  // 设置加载状态
  await nextTick()  // 等待 DOM 更新
  scrollToBottom()  // 滚动到底部
  try {
    // 获取当前选中的自定义模型配置
    const currentModelConfig = allAvailableModels.value.find(m => m.name === selectedModel.value)  // 查找当前模型配置
    // 调用封装的 API
    const data = await chatSessionApi.sendMessage(  // 发送消息到 API
      aiStore.currentSessionId!,  // 会话 ID
      content,  // 消息内容
      pdfId,  // PDF ID
      chatMode.value,  // 聊天模式
      selectedModel.value,  // 模型名称
      (currentModelConfig as CustomModel)?.apiBase,  // API 基础 URL
      (currentModelConfig as CustomModel)?.apiKey  // API 密钥
    )
    aiStore.addChatMessage({  // 添加助手消息到 UI
      role: 'assistant',  // 角色
      content: data.response,  // 响应内容
      citations: data.citations || []  // 引用数据
    })
  } catch (error) {
    console.error('Failed to send message:', error)  // 记录错误
    aiStore.addChatMessage({  // 添加错误消息
      role: 'assistant',
      content: '抱歉，网络请求失败，请检查后端服务。',
      citations: []
    })
  }
  aiStore.isLoadingChat = false  // 重置加载状态
  await nextTick()  // 等待 DOM 更新
  scrollToBottom()  // 滚动到底部
}

function scrollToBottom() {  // 滚动消息列表到底部的函数
  if (messagesContainer.value) {  // 如果容器存在
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight  // 设置滚动位置
  }
}

watch(() => aiStore.chatMessages.length, () => {  // 监听消息列表长度变化
  nextTick(scrollToBottom)  // 延迟滚动到底部
})

watch(() => libraryStore.currentDocument?.id, async (pdfId) => {  // 监听当前文档 ID 变化
  if (pdfId) {  // 如果有 PDF ID
    aiStore.clearChat()  // 清空聊天
    await aiStore.loadSessionsFromBackend(pdfId)  // 从后端加载会话
  }
}, { immediate: true })  // 立即执行

defineExpose({  // 暴露组件方法
  toggleHistoryPanel,  // 切换历史面板
  createNewChat  // 创建新聊天
})
</script>

<template>
  <div class="h-full flex flex-col relative">
    
    <!-- Tooltip Component (Global Absolute Position) -->
    <div 
      v-if="tooltipState.visible && tooltipState.content"
      class="fixed z-[100] w-80 bg-white dark:bg-[#2d2d30] rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 p-4 transition-opacity duration-200"
      :style="{ left: Math.min(tooltipState.x - 20, 1024) + 'px', top: (tooltipState.y - 10) + 'px', transform: 'translateY(-100%)' }"
      @mouseenter="handleTooltipEnter"
      @mouseleave="handleTooltipLeave"
    >
      <!-- Header: Icon + Type -->
      <div class="flex items-center gap-2 mb-2 text-xs font-bold uppercase tracking-wider text-gray-400">
        <span v-if="tooltipState.content.source_type === 'local'" class="flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          本地文档 - P{{ tooltipState.content.page || 'N/A' }}
        </span>
        <span v-else class="flex items-center gap-1 text-blue-500">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>
          网络来源
        </span>
      </div>
      
      <!-- Title -->
      <h4 class="font-semibold text-sm text-gray-800 dark:text-gray-100 mb-2 leading-tight">
        {{ tooltipState.content.title }}
      </h4>

      <!-- Snippet -->
      <p class="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-black/20 p-2 rounded mb-2 border-l-2 border-primary-400 line-clamp-4 italic">
        "{{ tooltipState.content.snippet }}"
      </p>

      <!-- Action Hint -->
      <div v-if="tooltipState.content.source_type === 'external'" class="text-xs text-blue-600 dark:text-blue-400 flex items-center justify-end gap-1">
        点击跳转原文 <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
      </div>
    </div>

    <!-- Custom Model Modal -->
    <div v-if="showCustomModelModal" class="absolute inset-0 bg-black/50 z-[60] flex items-center justify-center p-4">
      <div class="bg-white dark:bg-[#252526] rounded-xl w-full max-w-sm p-5 border border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-100">自定义模型</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-gray-500 mb-1">模型名称 (Model Name)</label>
            <input v-model="newCustomModel.name" type="text" placeholder="e.g. deepseek-chat" class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">API Base URL</label>
            <input v-model="newCustomModel.apiBase" type="text" placeholder="https://api.example.com/v1" class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">API Key</label>
            <input v-model="newCustomModel.apiKey" type="password" placeholder="sk-..." class="w-full px-3 py-2 text-sm border rounded-lg dark:bg-[#3e3e42] dark:border-gray-600 dark:text-white" />
          </div>
        </div>
        <div class="flex gap-2 mt-6">
          <button @click="showCustomModelModal = false" class="flex-1 px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg dark:text-gray-300 dark:hover:bg-gray-700">取消</button>
          <button @click="saveCustomModel" class="flex-1 px-4 py-2 text-sm text-white bg-primary-600 hover:bg-primary-700 rounded-lg">保存 (本地)</button>
        </div>
      </div>
    </div>

    <!-- History Panel (Overlay) -->
    <div
      v-if="showHistoryPanel"
      class="absolute inset-0 bg-black/20 z-20"
      @click="showHistoryPanel = false"
    >
      <div
        class="absolute right-0 top-0 bottom-0 w-80 bg-white/95 dark:bg-[#252526] backdrop-blur-md border-l border-gray-200/50 dark:border-gray-800/50"
        @click.stop
      >
        <!-- History Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200 tracking-wide">聊天记录</h3>
          <button
            @click="showHistoryPanel = false"
            class="p-1.5 hover:bg-gray-100 dark:hover:bg-[#3e3e42] rounded-lg transition-all duration-200"
          >
            <svg class="w-4 h-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <!-- History List -->
        <div class="overflow-y-auto" style="height: calc(100% - 65px)">
          <div v-if="getCurrentPdfSessions().length === 0" class="p-8 text-center text-gray-400 text-sm">暂无聊天记录</div>
          <div
            v-for="session in getCurrentPdfSessions()"
            :key="session.id"
            class="relative group/item"
          >
            <button
              @click="loadChatSession(session.id)"
              class="w-full text-left px-5 py-3.5 pr-12 hover:bg-gray-50/80 dark:hover:bg-[#2d2d30] border-b border-gray-50 dark:border-gray-800 transition-all duration-200"
              :class="{ 'bg-gray-50 dark:bg-[#2d2d30]': session.id === aiStore.currentSessionId }"
            >
              <div class="font-medium text-sm text-gray-800 dark:text-gray-200 truncate mb-1.5">{{ session.title }}</div>
              <div class="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                <span>{{ session.messages.length }} 条消息</span>
                <span>{{ formatTime(session.updatedAt) }}</span>
              </div>
            </button>
            <button
              @click="deleteChatSession(session.id, $event)"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover/item:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-all"
            >
              <svg class="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages Area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-6">
      <template v-if="aiStore.chatMessages.length > 0">
        <div v-for="message in aiStore.chatMessages" :key="message.id" :class="[message.role === 'user' ? 'max-w-[85%] ml-auto' : 'w-full']">
          
          <!-- User Message -->
          <div v-if="message.role === 'user'" class="px-5 py-3.5 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100/80 dark:from-[#2d2d30] dark:to-[#3e3e42] text-gray-800 dark:text-gray-200 rounded-br-md border border-gray-100/50 dark:border-gray-700/50 shadow-sm">
            <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ message.content }}</p>
          </div>
          
          <!-- Assistant Message -->
          <div v-else class="space-y-4 pl-1 pr-4">
            <!-- 1. Content with Citations -->
            <div 
              class="markdown-body prose prose-sm max-w-none dark:prose-invert 
                     prose-p:leading-relaxed prose-pre:bg-[#282c34] prose-pre:m-0
                     prose-headings:font-semibold prose-headings:text-gray-800 dark:prose-headings:text-gray-100
                     prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
                     text-gray-800 dark:text-gray-200"
              v-html="renderMarkdown(message.content)"
              @mouseover="handleMessageMouseOver($event, message.citations || [])"
              @mouseout="handleMessageMouseOut"
              @click="handleMessageClick($event, message.citations || [])"
            ></div>
            
            <!-- 2. Structured Reference List (Bottom) -->
            <div v-if="message.citations && message.citations.length > 0" class="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/50">
              <h4 class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">参考来源</h4>
              <div class="grid grid-cols-1 gap-2">
                <div 
                  v-for="cite in message.citations" 
                  :key="cite.id"
                  class="flex items-start gap-3 p-2 rounded-lg border border-transparent hover:border-gray-200 dark:hover:border-gray-700 hover:bg-gray-50 dark:hover:bg-[#3e3e42] transition-colors group"
                >
                  <!-- Index Badge -->
                  <div class="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[10px] font-bold text-primary-600 bg-primary-50 rounded mt-0.5">
                    {{ cite.id }}
                  </div>
                  
                  <!-- Content -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <span v-if="cite.source_type === 'local'" class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">PDF</span>
                      <span v-else class="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">Web</span>
                      
                      <a 
                        v-if="cite.source_type === 'external' && cite.url"
                        :href="cite.url" 
                        target="_blank"
                        class="text-xs font-medium text-gray-800 dark:text-gray-200 hover:text-blue-600 dark:hover:text-blue-400 truncate block"
                      >
                        {{ cite.title }}
                      </a>
                      <span v-else class="text-xs font-medium text-gray-800 dark:text-gray-200 truncate block">
                        {{ cite.title }}
                      </span>
                    </div>
                    
                    <p class="text-xs text-gray-400 truncate">
                      {{ cite.snippet }}
                    </p>
                  </div>

                  <!-- Action Icon (External Link) -->
                  <a 
                     v-if="cite.source_type === 'external' && cite.url"
                     :href="cite.url"
                     target="_blank"
                     class="flex-shrink-0 text-gray-300 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                     title="打开链接"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
          
          <p class="text-xs text-gray-400 mt-1 px-1" :class="message.role === 'user' ? 'text-right' : ''">{{ message.timestamp.toLocaleTimeString() }}</p>
        </div>
        
        <div v-if="aiStore.isLoadingChat" class="flex items-center gap-2 text-gray-500 p-4">
          <div class="flex gap-1"><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-75"></span><span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-150"></span></div>
          <span class="text-sm">正在深度思考...</span>
        </div>
      </template>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-t border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-[#252526]/50 backdrop-blur-sm" @click.self="closeMenus">
      <!-- Preview boxes -->
      <div v-if="selectedReferences.length > 0 || attachedFiles.length > 0 || pdfStore.selectedText" class="flex flex-wrap gap-1.5 mb-2">
        <!-- PDF Selection Preview -->
        <div v-if="pdfStore.selectedText" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-xs">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" /></svg>
          <span class="max-w-20 truncate" :title="pdfStore.selectedText">{{ pdfStore.selectedText }}</span>
          <button @click="pdfStore.clearSelection()" class="hover:text-gray-900 dark:hover:text-white"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>

        <div v-for="ref in selectedReferences" :key="ref.id" class="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 text-primary-700 rounded text-xs">
          <span class="text-primary-500">@</span><span class="max-w-20 truncate">{{ ref.label }}</span>
          <button @click="removeReference(ref.id)" class="hover:text-primary-900"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>
        <div v-for="file in attachedFiles" :key="file.id" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
          <span class="max-w-20 truncate">{{ file.name }}</span>
          <button @click="removeFile(file.id)" class="hover:text-gray-900"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
        </div>
      </div>

      <!-- Toolbar buttons -->
      <div class="flex items-center gap-1 mb-2">
        
        <!-- Feature 2: Prompts Menu -->
        <div class="relative">
          <button
            @click="togglePromptMenu"
            class="flex items-center gap-0.5 p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 transition-colors"
            :class="{ 'bg-gray-100': showPromptMenu }"
            title="预设提示词"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
          </button>
          
          <!-- Prompt Dropdown -->
          <div v-if="showPromptMenu" class="absolute bottom-full left-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-2 min-w-64 max-w-sm z-50">
            <div class="flex items-center justify-between px-3 pb-2 border-b border-gray-100 dark:border-gray-700 mb-1">
              <span class="text-xs font-semibold text-gray-500">提示词</span>
              <div class="flex gap-1">
                <button v-if="isEditingPrompts" @click="addNewPrompt" class="p-1 text-primary-700 hover:bg-primary-50 rounded transition-colors" title="新增提示词">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                </button>
                <button @click="isEditingPrompts ? savePrompts() : toggleEditPrompts()" class="p-1 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors" :title="isEditingPrompts ? '保存' : '编辑'">
                  <svg v-if="isEditingPrompts" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                  <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                </button>
              </div>
            </div>
            
            <div class="max-h-60 overflow-y-auto">
              <div v-if="isEditingPrompts" class="px-2 space-y-1">
                <div v-for="(prompt, index) in userPrompts" :key="prompt.id" class="flex items-center gap-1">
                  <input v-model="prompt.text" type="text" class="flex-1 text-xs border border-gray-200 rounded px-2 py-1.5 focus:border-primary-500 outline-none" placeholder="输入提示词..." />
                  <button @click="removePrompt(index)" class="p-1 text-gray-400 hover:text-red-500"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
                </div>
              </div>
              <div v-else>
                 <button
                  v-for="prompt in userPrompts"
                  :key="prompt.id"
                  @click="handlePromptClick(prompt.text)"
                  class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-[#3e3e42] truncate"
                  :title="prompt.text"
                >
                  {{ prompt.text }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- @ Button -->
        <div class="relative">
          <button @click="toggleAtMenu" class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors text-sm font-medium" :class="{ 'bg-gray-100 text-gray-700': showAtMenu }" title="插入引用">@</button>
          <div v-if="showAtMenu" class="absolute bottom-full left-0 mb-1 bg-gray-800/90 rounded-lg py-1 min-w-36 z-50">
            <div class="relative">
              <button @click="handleKeywordClick" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center justify-between"><span>本文关键词</span><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg></button>
              <div v-if="showKeywordSubmenu" class="absolute left-full top-0 ml-1 bg-gray-800/90 rounded-lg py-1 min-w-32">
                <button @click="selectFrameMode" class="w-full text-left px-3 py-2 text-sm text-white hover:bg-gray-700/50 flex items-center gap-2">框选模式</button>
                <div class="border-t border-gray-600 my-1"></div>
                <div class="px-2 py-1 text-xs text-gray-400">已建立索引</div>
                <button v-for="kw in keywordIndexes" :key="kw.id" @click="selectKeywordIndex(kw)" class="w-full text-left px-3 py-1.5 text-sm text-white hover:bg-gray-700/50">{{ kw.label }}</button>
              </div>
            </div>
            <button class="w-full text-left px-3 py-2 text-sm text-gray-400 cursor-not-allowed">已读论文</button>
          </div>
        </div>

        <!-- Attachment -->
        <button @click="triggerFileInput" class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors" title="添加文件">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
        </button>
        <input ref="fileInput" type="file" multiple class="hidden" @change="handleFileSelect" />

        <!-- Chat Mode Toggle Button -->
        <button 
          @click="toggleChatMode" 
          class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          :title="chatMode === 'agent' ? '当前: Agent 模式 (点击切换到简单聊天)' : '当前: 简单聊天模式 (点击切换到 Agent )'"
        >
          <svg v-if="chatMode === 'agent'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        </button>

        <!-- Feature 3: Model Selector with Custom Models -->
        <div class="relative ml-auto">
          <button @click="toggleModelMenu" class="flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors text-xs" :class="{ 'bg-gray-100 dark:bg-gray-700': showModelMenu }">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
            <span class="max-w-24 truncate">{{ selectedModel }}</span>
            <svg class="w-3 h-3 transition-transform" :class="{ 'rotate-180': showModelMenu }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
          </button>
          <div v-if="showModelMenu" class="absolute bottom-full right-0 mb-1 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded-lg py-1 min-w-36 max-w-48 z-50">
            <button @click="selectModel('README Fusion')" class="w-full text-left px-2.5 py-2 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 transition-colors" :class="{ 'bg-gray-400/50 dark:bg-gray-600/50': selectedModel === 'README Fusion' }">README Fusion</button>
            
            <!-- Custom Models Section -->
            <template v-if="customModels.length > 0">
              <div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
              <div v-for="model in customModels" :key="model.id" class="relative group">
                <button @click="selectModel(model.name)" class="w-full text-left px-2.5 py-2 pr-7 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 transition-colors truncate" :class="{ 'bg-gray-400/50 dark:bg-gray-600/50': selectedModel === model.name }">
                  {{ model.name }}
                </button>
                <button @click="deleteCustomModel(model.id, $event)" class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 opacity-0 group-hover:opacity-100 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-all"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
              </div>
            </template>
            
            <div class="border-t border-gray-200 dark:border-gray-600 my-1"></div>
            <button @click="openCustomModelModal" class="w-full text-left px-2.5 py-2 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-400/50 dark:hover:bg-gray-600/50 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
              + 添加自定义模型
            </button>
          </div>
        </div>
      </div>

      <!-- Feature 1: Clean Input Area & Send Button -->
      <div class="flex gap-2 items-end">
        <div class="flex-1 relative">
           <textarea
            v-model="inputMessage"
            placeholder="输入问题..."
            @keyup.enter.exact.prevent="sendMessage()"
            class="w-full px-4 py-3 min-h-[46px] max-h-32 border border-gray-200 dark:border-gray-700 rounded-2xl focus:outline-none focus:border-gray-300 dark:focus:border-gray-600 focus:ring-2 focus:ring-gray-100 dark:focus:ring-gray-800 text-sm bg-white dark:bg-[#3e3e42] dark:text-gray-200 transition-all duration-200 placeholder:text-gray-400 resize-none overflow-hidden"
            style="field-sizing: content;" 
          ></textarea>
        </div>
        
        <button
          @click="sendMessage()"
          :disabled="!inputMessage.trim() || aiStore.isLoadingChat"
          class="mb-1 p-2.5 rounded-xl transition-all duration-200 flex-shrink-0"
          :class="[
            inputMessage.trim() 
              ? 'bg-gray-900 dark:bg-[#0e639c] text-white hover:bg-gray-800 dark:hover:bg-[#1177bb]' 
              : 'bg-gray-100 dark:bg-[#2d2d30] text-gray-400 dark:text-gray-500 cursor-not-allowed'
          ]"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style>
/* 自定义 Markdown 样式微调，解决 Tailwind Typography 在聊天气泡中的一些间距问题 */
.markdown-body > :first-child {
  margin-top: 0 !important;
}
.markdown-body > :last-child {
  margin-bottom: 0 !important;
}
.markdown-body ul {
  list-style-type: disc;
  padding-left: 1.5em;
}
.markdown-body ol {
  list-style-type: decimal;
  padding-left: 1.5em;
}
/* 调整代码块字体 */
.markdown-body code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
/* 简单的行内代码样式 */
.markdown-body :not(pre) > code {
  background-color: rgba(100, 116, 139, 0.1);
  color: #eb5757;
  padding: 0.2em 0.4em;
  border-radius: 0.25rem;
  font-size: 0.875em;
}
.dark .markdown-body :not(pre) > code {
  background-color: rgba(255, 255, 255, 0.1);
  color: #ff7b72;
}

/* 引用标签悬浮效果 */
.citation-ref:hover {
  text-decoration: underline;
}
</style>
