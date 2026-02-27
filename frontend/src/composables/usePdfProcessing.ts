import { ref } from 'vue'
import { pdfApi } from '../api'
import { usePdfStore } from '../stores/pdf'
import { useTranslationStore } from '../stores/translation'

type PdfProcessStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'unknown'
const POLL_INTERVAL_MS = 2000
const MAX_RETRIES = 3

// 全局单例状态，防止多组件重复轮询同一文件
const parsingStatus = ref<Record<string, PdfProcessStatus>>({})
const receivedUpToPage: Record<string, number> = {}
const pollTimers: Record<string, ReturnType<typeof setTimeout>> = {}

export function usePdfProcessing() {
    const pdfStore = usePdfStore()
    const translationStore = useTranslationStore()

    async function _fetchOnce(pdfId: string, retries = 0): Promise<boolean> {
        const fromPage = (receivedUpToPage[pdfId] ?? 0) + 1

        try {
            const result = await pdfApi.getStatus(pdfId, fromPage)

            if (result.paragraphs && result.paragraphs.length > 0) {
                pdfStore.appendParagraphs(pdfId, result.paragraphs)

                for (const p of result.paragraphs) {
                    if (p.id && p.translation) {
                        translationStore.translatedParagraphsCache.set(p.id, p.translation)
                    }
                }
            }

            if (result.currentPage > (receivedUpToPage[pdfId] ?? 0)) {
                receivedUpToPage[pdfId] = result.currentPage
            }

            parsingStatus.value[pdfId] = result.status

            if (result.status === 'completed' || result.status === 'failed') {
                return false // 停止轮询
            }

            return true
        } catch (err) {
            console.warn(`[usePdfProcessing] Status fetch failed for ${pdfId}:`, err)
            if (retries < MAX_RETRIES) {
                await new Promise(r => setTimeout(r, POLL_INTERVAL_MS * (retries + 1)))
                return _fetchOnce(pdfId, retries + 1)
            }
            parsingStatus.value[pdfId] = 'failed'
            return false
        }
    }

    async function _schedulePoll(pdfId: string) {
        const shouldContinue = await _fetchOnce(pdfId)
        if (shouldContinue && pdfId in pollTimers) {
            pollTimers[pdfId] = setTimeout(() => _schedulePoll(pdfId), POLL_INTERVAL_MS)
        } else {
            delete pollTimers[pdfId]
        }
    }

    async function startPolling(pdfId: string) {
        if (parsingStatus.value[pdfId] === 'completed') return
        if (pdfId in pollTimers) return

        parsingStatus.value[pdfId] = parsingStatus.value[pdfId] ?? 'pending'
        pollTimers[pdfId] = setTimeout(() => { }, 0) // 占位标记正在轮询
        await _schedulePoll(pdfId)
    }

    function stopPolling(pdfId: string) {
        if (pdfId in pollTimers) {
            clearTimeout(pollTimers[pdfId])
            delete pollTimers[pdfId]
        }
    }

    function isParsed(pdfId: string): boolean {
        return parsingStatus.value[pdfId] === 'completed'
    }

    return {
        startPolling,
        stopPolling,
        isParsed,
    }
}
