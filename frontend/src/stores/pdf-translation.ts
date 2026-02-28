import { ref } from 'vue'
import type { PdfParagraph } from '../types'

export function usePdfTranslationState() {
    // 记录每一页的翻译状态: 'idle' | 'loading' | 'done' | 'error'
    const pageTranslationStatus = ref<Record<number, 'idle' | 'loading' | 'done' | 'error'>>({})
    // 全文翻译状态
    const fullTranslationStatus = ref<'idle' | 'loading' | 'done' | 'error'>('idle')

    /**
     * 预翻译核心逻辑：翻译指定页面的所有段落
     */
    async function startPagePreTranslation(
        pageNumber: number,
        pdfId: string,
        allParagraphs: Record<string, PdfParagraph[]>,
        skipIfProcessing = true
    ) {
        if (skipIfProcessing && pageTranslationStatus.value[pageNumber] === 'loading') {
            return
        }

        const docParagraphs = allParagraphs[pdfId]
        if (!docParagraphs) return

        const pageParagraphs = docParagraphs.filter(p => p.page === pageNumber)
        if (!pageParagraphs.length) {
            pageTranslationStatus.value[pageNumber] = 'done'
            return
        }

        pageTranslationStatus.value[pageNumber] = 'loading'

        const { useTranslationStore } = await import('./translation')
        const translationStore = useTranslationStore()
        const { aiApi } = await import('../api')

        let allSuccess = true

        for (const p of pageParagraphs) {
            if (translationStore.getCachedTranslation(p.id)) {
                continue
            }
            try {
                const result = await aiApi.translateParagraph(pdfId, p.id)
                if (result.success) {
                    translationStore.setTranslation(p.id, result.translation)
                } else {
                    allSuccess = false
                }
            } catch (error) {
                console.error(`[Pre-translate] Failed for paragraph ${p.id}:`, error)
                allSuccess = false
            }
        }

        pageTranslationStatus.value[pageNumber] = allSuccess ? 'done' : 'error'
        return allSuccess
    }

    /**
     * 全文预翻译：按页序执行
     */
    async function startFullPreTranslation(
        pdfId: string,
        totalPages: number,
        allParagraphs: Record<string, PdfParagraph[]>,
        startPagePreTranslationFn: typeof startPagePreTranslation
    ) {
        if (fullTranslationStatus.value === 'loading') return

        fullTranslationStatus.value = 'loading'
        let hasError = false

        try {
            for (let i = 1; i <= totalPages; i++) {
                const success = await startPagePreTranslationFn(i, pdfId, allParagraphs, true)
                if (success === false) hasError = true
            }
            fullTranslationStatus.value = hasError ? 'error' : 'done'
        } catch (e) {
            console.error('[Full Pre-translate] Interrupted:', e)
            fullTranslationStatus.value = 'error'
        }
    }

    return {
        pageTranslationStatus,
        fullTranslationStatus,
        startPagePreTranslation,
        startFullPreTranslation
    }
}
