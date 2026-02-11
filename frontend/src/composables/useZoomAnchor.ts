/**
 * 缩放锚点管理 Composable
 * 处理缩放时的位置捕获和恢复
 */

import { ref, type Ref } from 'vue'
import { nextTick } from 'vue'
import type { ZoomAnchor, PageRef } from '../types/pdf'
import { getPageTop, getScaledPageSize, getPageAtY } from '../utils/PdfHelper'
import type { PageSize } from '../types/pdf'

export function useZoomAnchor(
  containerRef: Ref<HTMLElement | null>,
  pageNumbers: Ref<number[]>,
  pageRefs: Map<number, PageRef>,
  pageSizesConstant: Ref<PageSize | null>,
  pageHeightAccumulator: Ref<number[]>,
  scale: Ref<number>
) {
  const pendingAnchor = ref<ZoomAnchor | null>(null)

  /**
   * 捕获当前的中心锚点，用于缩放后恢复位置
   * @param mousePos - 可选的鼠标位置（相对于视口坐标）
   */
  function captureCenterAnchor(mousePos?: { x: number; y: number }): ZoomAnchor | null {
    const container = containerRef.value
    if (!container || !pageNumbers.value.length) return null

    const rect = container.getBoundingClientRect()

    const targetX = mousePos
      ? (mousePos.x - rect.left + container.scrollLeft)
      : (container.scrollLeft + container.clientWidth / 2)

    const targetY = mousePos
      ? (mousePos.y - rect.top + container.scrollTop)
      : (container.scrollTop + container.clientHeight / 2)

    let anchor: ZoomAnchor | null = null

    // 使用计算/二分法快速定位页面
    const page = getPageAtY(
      targetY,
      pageNumbers.value.length,
      scale.value,
      pageSizesConstant.value,
      pageHeightAccumulator.value
    )

    if (page) {
      const refs = pageRefs.get(page)
      const size = getScaledPageSize(
        page,
        scale.value,
        pageSizesConstant.value,
        null
      )

      if (refs) {
        const pageTop = refs.container.offsetTop
        const pageLeft = refs.container.offsetLeft
        const height = refs.container.offsetHeight || size.height
        const width = refs.container.offsetWidth || size.width

        anchor = {
          page,
          ratioY: (targetY - pageTop) / height,
          ratioX: (targetX - pageLeft) / width,
          destX: mousePos ? mousePos.x - rect.left : undefined,
          destY: mousePos ? mousePos.y - rect.top : undefined
        }
      } else {
        const calculatedTop = getPageTop(
          page,
          scale.value,
          pageSizesConstant.value,
          pageHeightAccumulator.value
        )

        anchor = {
          page,
          ratioY: (targetY - calculatedTop) / size.height,
          ratioX: 0.5,
          destX: mousePos ? mousePos.x - rect.left : undefined,
          destY: mousePos ? mousePos.y - rect.top : undefined
        }
      }
    }

    return anchor
  }

  /**
   * 恢复缩放前的位置锚点
   */
  function restoreAnchor(anchor: ZoomAnchor): void {
    const container = containerRef.value
    if (!container) return

    const refs = pageRefs.get(anchor.page)
    if (!refs) {
      nextTick(() => {
        if (pendingAnchor.value) {
          restoreAnchor(pendingAnchor.value)
        }
      })
      return
    }

    const height = refs.container.offsetHeight || refs.container.clientHeight
    const width = refs.container.offsetWidth || refs.container.clientWidth
    if (!height) return

    const currentContentY = refs.container.offsetTop + anchor.ratioY * height
    const currentContentX = refs.container.offsetLeft + anchor.ratioX * width

    let top = 0
    let left = 0

    if (anchor.destX !== undefined && anchor.destY !== undefined) {
      top = currentContentY - anchor.destY
      left = currentContentX - anchor.destX
    } else {
      top = currentContentY - container.clientHeight / 2
      left = currentContentX - container.clientWidth / 2
    }

    container.scrollTo({
      top: Math.round(top),
      left: Math.round(left),
      behavior: 'instant' as ScrollBehavior
    })
  }

  /**
   * 设置待处理的锚点
   */
  function setPendingAnchor(anchor: ZoomAnchor | null): void {
    pendingAnchor.value = anchor
  }

  /**
   * 清除待处理的锚点
   */
  function clearPendingAnchor(): void {
    pendingAnchor.value = null
  }

  return {
    pendingAnchor,
    captureCenterAnchor,
    restoreAnchor,
    setPendingAnchor,
    clearPendingAnchor
  }
}
