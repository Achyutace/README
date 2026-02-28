import { ref } from 'vue'
import type { InternalLinkData } from '../types'

/** PDF 内部链接目标坐标 */
export type DestinationCoords = {
    page: number
    x: number | null
    y: number | null
    zoom: number | null
    type: string
}

export function usePdfUiState() {
    // ---------------------- 笔记预览卡片 ----------------------
    const notePreviewCard = ref<{
        isVisible: boolean
        note: { id: number | string; title: string; content: string } | null
        position: { x: number; y: number }
    }>({
        isVisible: false,
        note: null,
        position: { x: 0, y: 0 }
    })

    function openNotePreviewCard(note: { id: number | string; title: string; content: string }, position: { x: number; y: number }) {
        notePreviewCard.value = { isVisible: true, note, position }
    }

    function closeNotePreviewCard() {
        notePreviewCard.value = { isVisible: false, note: null, position: { x: 0, y: 0 } }
    }

    function updateNotePreviewPosition(position: { x: number; y: number }) {
        notePreviewCard.value.position = position
    }

    // ---------------------- 智能引用卡片 ----------------------
    const smartRefCard = ref<{
        isVisible: boolean
        isLoading: boolean
        paper: any | null
        position: { x: number; y: number }
        error?: string | null
    }>({
        isVisible: false,
        isLoading: false,
        paper: null,
        position: { x: 0, y: 0 },
        error: null
    })

    function openSmartRefCard(paperData: any, position: { x: number; y: number }) {
        smartRefCard.value = { isVisible: true, isLoading: false, paper: paperData, position, error: null }
    }

    function closeSmartRefCard() {
        smartRefCard.value.isVisible = false
    }

    function updateSmartRefPosition(position: { x: number; y: number }) {
        smartRefCard.value.position = position
    }

    // ---------------------- 内部链接弹窗 ----------------------
    const internalLinkPopup = ref<{
        isVisible: boolean
        destCoords: DestinationCoords | null
        position: { x: number; y: number }
        linkData: InternalLinkData | null
        paragraphContent: string | null
        isLoading: boolean
        error: string | null
    }>({
        isVisible: false,
        destCoords: null,
        position: { x: 0, y: 0 },
        linkData: null,
        paragraphContent: null,
        isLoading: false,
        error: null
    })

    function openInternalLinkPopup(destCoords: DestinationCoords, position: { x: number; y: number }) {
        internalLinkPopup.value = {
            isVisible: true,
            destCoords,
            position,
            linkData: null,
            paragraphContent: null,
            isLoading: false,
            error: null
        }
    }

    function closeInternalLinkPopup() {
        internalLinkPopup.value.isVisible = false
    }

    function updateInternalLinkPopupPosition(position: { x: number; y: number }) {
        internalLinkPopup.value.position = position
    }

    function setInternalLinkData(data: InternalLinkData | null, paragraphContent?: string, error?: string) {
        internalLinkPopup.value.linkData = data
        internalLinkPopup.value.paragraphContent = paragraphContent || null
        internalLinkPopup.value.error = error || null
    }

    function setInternalLinkLoading(loading: boolean) {
        internalLinkPopup.value.isLoading = loading
    }

    return {
        notePreviewCard,
        openNotePreviewCard,
        closeNotePreviewCard,
        updateNotePreviewPosition,
        smartRefCard,
        openSmartRefCard,
        closeSmartRefCard,
        updateSmartRefPosition,
        internalLinkPopup,
        openInternalLinkPopup,
        closeInternalLinkPopup,
        updateInternalLinkPopupPosition,
        setInternalLinkData,
        setInternalLinkLoading,
    }
}
