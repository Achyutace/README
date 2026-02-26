import { reactive } from 'vue'
import MarkdownIt from 'markdown-it'
import type { Options } from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import 'highlight.js/styles/atom-one-dark.css'
import type { Citation } from '../types'

export function useMarkdownRenderer() {
    const tooltipState = reactive({
        visible: false,
        x: 0,
        y: 0,
        content: null as Citation | null
    })

    let tooltipTimeout: ReturnType<typeof setTimeout> | null = null

    const md: MarkdownIt = new MarkdownIt({
        html: false,
        linkify: true,
        breaks: true,
        highlight: function (str: string, lang: string): string {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
                        }</code></pre>`
                } catch (__) { }
            }
            return `<pre class="hljs p-3 rounded-lg text-xs overflow-x-auto"><code>${md.utils.escapeHtml(str)}</code></pre>`
        }
    } as Options)

    const renderMarkdown = (content: string) => {
        if (!content) return ''

        let html = md.render(content)

        html = html.replace(/\[(\d+)\]/g, (_match, id) => {
            return `<span class="citation-ref text-primary-600 bg-primary-50 px-1 rounded cursor-pointer font-medium hover:bg-primary-100 transition-colors select-none" data-id="${id}">[${id}]</span>`
        })

        return DOMPurify.sanitize(html, {
            ADD_TAGS: ['iframe'],
            ADD_ATTR: ['target', 'data-id', 'class']
        })
    }

    // #11: 使用 getBoundingClientRect() 直接获取视口坐标，配合模板中 fixed 定位使用
    const handleMessageMouseOver = (event: MouseEvent, citations: Citation[]) => {
        const target = event.target as HTMLElement
        if (target.classList.contains('citation-ref')) {
            const index = parseInt(target.getAttribute('data-id') || '0') - 1
            const citationData = citations[index]

            if (citationData) {
                if (tooltipTimeout) clearTimeout(tooltipTimeout)

                const rect = target.getBoundingClientRect()
                tooltipState.x = rect.left
                tooltipState.y = rect.top - 10
                tooltipState.content = citationData
                tooltipState.visible = true
            }
        }
    }

    const handleMessageMouseOut = (event: MouseEvent) => {
        const target = event.target as HTMLElement
        if (target.classList.contains('citation-ref')) {
            tooltipTimeout = setTimeout(() => {
                tooltipState.visible = false
                tooltipState.content = null
            }, 300)
        }
    }

    const handleMessageClick = (event: MouseEvent, citations: Citation[]) => {
        const target = event.target as HTMLElement
        if (target.classList.contains('citation-ref')) {
            const index = parseInt(target.getAttribute('data-id') || '0') - 1
            const citationData = citations[index]

            if (citationData && citationData.url) {
                window.open(citationData.url, '_blank')
            }
        }
    }

    const handleTooltipEnter = () => {
        if (tooltipTimeout) clearTimeout(tooltipTimeout)
    }

    const handleTooltipLeave = () => {
        tooltipState.visible = false
        tooltipState.content = null
    }

    return {
        tooltipState,
        renderMarkdown,
        handleMessageMouseOver,
        handleMessageMouseOut,
        handleMessageClick,
        handleTooltipEnter,
        handleTooltipLeave
    }
}
