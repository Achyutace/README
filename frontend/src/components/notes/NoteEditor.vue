<script setup lang="ts">
// ------------------------- 导入依赖与编辑器初始化 -------------------------
// 引入 TipTap 编辑器所需的扩展与 Vue 响应式 API
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { Markdown } from 'tiptap-markdown'
import Placeholder from '@tiptap/extension-placeholder'
import { watch, onBeforeUnmount } from 'vue'

const props = defineProps<{
  modelValue: string
  editable: boolean
}>()

const emit = defineEmits(['update:modelValue', 'save'])

const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit,
    // 支持 Markdown 语法输入和输出
    Markdown.configure({
      html: false,
      transformPastedText: true,
      transformCopiedText: true
    }),
    Placeholder.configure({
      placeholder: '输入内容 (支持 Markdown 语法，如 # 标题)...',
    }),
  ],
  editorProps: {
    // 集成 Tailwind 样式类到编辑器根元素
    attributes: {
      class: 'max-w-none focus:outline-none markdown-content',
    },
  },
  onUpdate: ({ editor }) => {
    // 获取 Markdown 内容并更新
    const storage = editor.storage as any
    const markdown = storage.markdown?.getMarkdown() || editor.getText()
    emit('update:modelValue', markdown)
  },
})

// 监听外部 editable 变化（比如点击完成/编辑按钮）
watch(() => props.editable, (isEditable) => {
  editor.value?.setEditable(isEditable)
})

// 监听外部内容变化（比如加载新文档）
watch(() => props.modelValue, (newValue) => {
  if (editor.value) {
    const storage = editor.value.storage as any
    const currentMarkdown = storage.markdown?.getMarkdown() || editor.value.getText()
    // 只有当内容真正改变时才重置（防止光标跳动）
    if (newValue !== currentMarkdown) {
      editor.value.commands.setContent(newValue)
    }
  }
})

onBeforeUnmount(() => {
  editor.value?.destroy()
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
