<script setup lang="ts">
// ------------------------- 导入依赖与编辑器初始化 -------------------------
// 引入 TipTap 编辑器所需的扩展与 Vue 响应式 API
import { useEditor, EditorContent } from '@tiptap/vue-3'  // 导入 TipTap 编辑器的 Vue 3 版本的主要组件
import StarterKit from '@tiptap/starter-kit'  // 导入基础编辑器扩展包，包含常用功能如粗体、斜体等
import { Markdown } from 'tiptap-markdown'  // 导入 Markdown 扩展，支持 Markdown 语法输入和输出
import Placeholder from '@tiptap/extension-placeholder'  // 导入占位符扩展，用于显示提示文本
import { watch, onBeforeUnmount } from 'vue'  // 导入 Vue 的响应式监听和生命周期钩子

// 定义组件的 props，接收外部传入的模型值和可编辑状态
const props = defineProps<{
  modelValue: string  // 双向绑定的内容值
  editable: boolean  // 是否可编辑
}>()

// 定义组件的 emits，用于向父组件发送事件
const emit = defineEmits(['update:modelValue', 'save'])  // 发出更新模型值和保存事件

// 创建 TipTap 编辑器实例
const editor = useEditor({
  content: props.modelValue,  // 设置编辑器的初始内容
  editable: props.editable,  // 设置编辑器是否可编辑
  extensions: [  // 配置编辑器的扩展
    StarterKit,  // 添加基础扩展
    // 支持 Markdown 语法输入和输出
    Markdown.configure({  // 配置 Markdown 扩展
      html: false,  // 禁用 HTML 输出，确保安全
      transformPastedText: true,  // 转换粘贴的文本为 Markdown
      transformCopiedText: true  // 转换复制的文本为 Markdown
    }),
    Placeholder.configure({  // 配置占位符扩展
      placeholder: '输入内容 (支持 Markdown 语法，如 # 标题)...',  // 设置占位符文本
    }),
  ],
  editorProps: {  // 配置编辑器的属性
    // 集成 Tailwind 样式类到编辑器根元素
    attributes: {  // 设置编辑器根元素的属性
      class: 'max-w-none focus:outline-none markdown-content',  // 添加 CSS 类
    },
  },
  onUpdate: ({ editor }) => {  // 编辑器内容更新时的回调
    // 获取 Markdown 内容并更新
    const storage = editor.storage as any  // 获取编辑器的存储对象
    const markdown = storage.markdown?.getMarkdown() || editor.getText()  // 获取 Markdown 内容或纯文本
    emit('update:modelValue', markdown)  // 发出更新事件
  },
})

// 监听外部 editable 变化（比如点击完成/编辑按钮）
watch(() => props.editable, (isEditable) => {  // 监听 props.editable 的变化
  editor.value?.setEditable(isEditable)  // 设置编辑器的可编辑状态
})

// 监听外部内容变化（比如加载新文档）
watch(() => props.modelValue, (newValue) => {  // 监听 props.modelValue 的变化
  if (editor.value) {  // 如果编辑器实例存在
    const storage = editor.value.storage as any  // 获取存储对象
    const currentMarkdown = storage.markdown?.getMarkdown() || editor.value.getText()  // 获取当前内容
    // 只有当内容真正改变时才重置（防止光标跳动）
    if (newValue !== currentMarkdown) {  // 如果新内容与当前内容不同
      editor.value.commands.setContent(newValue)  // 重置编辑器内容
    }
  }
})

// 组件卸载前销毁编辑器实例
onBeforeUnmount(() => {  // 在组件卸载前执行
  editor.value?.destroy()  // 销毁编辑器实例，释放资源
})
</script>

<template>
  <editor-content :editor="editor" />
</template>

<style>
/* Tiptap 编辑器内部样式修正 */
.ProseMirror p.is-editor-empty:first-child::before {
  color: #9ca3af;
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
</style>
