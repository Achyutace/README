/**
 * 缩放管理 Composable
 * 处理缩放锚点捕获、位置恢复、缩放过渡效果
 */

import { ref, nextTick, type Ref } from 'vue'
import type { PageRef, ZoomAnchor } from '../types/pdf'
import type { PageGeometry } from './usePageGeometry'

export function useZoom(
  containerRef: Ref<HTMLElement | null>,
  pageRefs: Map<number, PageRef>,
  pageNumbers: Ref<number[]>,
  geometry: PageGeometry,
  scale: Ref<number>
) {
  // 状态
  const isZooming = ref(false)
  const pendingAnchor = ref<ZoomAnchor | null>(null)

  // 捕获当前的中心锚点，用于缩放后恢复位置
  // mousePos: 可选的鼠标位置（相对于视口坐标）
  function captureCenterAnchor(mousePos?: { x: number; y: number }): ZoomAnchor | null {
    const container = containerRef.value
    if (!container || !pageNumbers.value.length) return null

    // 返回该容器相对于视口（viewport）的矩形（DOMRect）
    const rect = container.getBoundingClientRect()

    // 目标内容坐标（相对于容器内容左上角 - 包含滚动距离）
    const targetX = mousePos
      ? (mousePos.x - rect.left + container.scrollLeft)
      : (container.scrollLeft + container.clientWidth / 2)

    const targetY = mousePos
      ? (mousePos.y - rect.top + container.scrollTop)
      : (container.scrollTop + container.clientHeight / 2)

    let anchor: ZoomAnchor | null = null

    // 使用计算/二分法快速定位页面
    const page = geometry.getPageAtY(targetY, pageNumbers.value.length)

    if (page) {
      const refs = pageRefs.get(page)
      const size = geometry.getScaledPageSize(page)

      if (refs) {
        // 使用实际 DOM 位置（最准确）
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
        // 如果页面未渲染（例如在虚拟列表中），使用计算位置作为兜底
        const calculatedTop = geometry.getPageTop(page)

        anchor = {
          page,
          ratioY: (targetY - calculatedTop) / size.height,
          ratioX: 0.5, // 默认水平居中
          destX: mousePos ? mousePos.x - rect.left : undefined,
          destY: mousePos ? mousePos.y - rect.top : undefined
        }
      }
    }

    return anchor
  }

  // 恢复缩放前的位置锚点
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

    // 计算原来那个内容点现在的位置
    const currentContentY = refs.container.offsetTop + anchor.ratioY * height
    const currentContentX = refs.container.offsetLeft + anchor.ratioX * width

    let top = 0
    let left = 0

    if (anchor.destX !== undefined && anchor.destY !== undefined) {
      // 鼠标缩放恢复模式：让内容点回到屏幕上的 dest 位置
      top = currentContentY - anchor.destY
      left = currentContentX - anchor.destX
    } else {
      // 中心缩放恢复模式：让内容点回到视口中心
      top = currentContentY - container.clientHeight / 2
      left = currentContentX - container.clientWidth / 2
    }

    // 吸附到整数像素，避免亚像素渲染导致模糊
    container.scrollTo({
      top: Math.round(top),
      left: Math.round(left),
      behavior: 'instant' as ScrollBehavior
    })
  }

  // 缩放手势进行时，先按目标尺寸拉伸已有渲染
  function applyInterimScale(
    lastRenderedScale: Map<number, number>
  ): void {
    pageRefs.forEach((refs, pageNumber) => {
      const size = geometry.getPageSize(pageNumber)
      if (!size) return

      const renderedScale = lastRenderedScale.get(pageNumber) ?? scale.value
      const targetScale = scale.value
      const ratio = renderedScale ? targetScale / renderedScale : 1

      // 基准尺寸：最后一次真实渲染时的尺寸（与文本层布局一致）
      const baseWidth = Math.floor(size.width * renderedScale)
      const baseHeight = Math.floor(size.height * renderedScale)
      // 目标尺寸：当前缩放下容器所需的可视尺寸
      const targetWidth = Math.floor(size.width * targetScale)
      const targetHeight = Math.floor(size.height * targetScale)

      // Canvas 直接用目标尺寸拉伸即可
      refs.canvas.style.width = `${targetWidth}px`
      refs.canvas.style.height = `${targetHeight}px`

      // 文本层保持"旧尺度"尺寸，通过 transform 过渡到新尺度，避免跟随过慢
      refs.textLayer.style.width = `${baseWidth}px`
      refs.textLayer.style.height = `${baseHeight}px`
      refs.textLayer.style.transformOrigin = 'top left'
      refs.textLayer.style.transform = `scale(${ratio})`

      // 链接层同样按旧尺寸 + 缩放，保证点击区域同步
      refs.linkLayer.style.width = `${baseWidth}px`
      refs.linkLayer.style.height = `${baseHeight}px`
      refs.linkLayer.style.transformOrigin = 'top left'
      refs.linkLayer.style.transform = `scale(${ratio})`

      // 高亮层同步缩放，避免在缩放过渡时错位
      refs.highlightLayer.style.width = `${baseWidth}px`
      refs.highlightLayer.style.height = `${baseHeight}px`
      refs.highlightLayer.style.transformOrigin = 'top left'
      refs.highlightLayer.style.transform = `scale(${ratio})`
    })
  }

  // 设置缩放状态
  function setZooming(value: boolean): void {
    isZooming.value = value
  }

  // 设置待处理锚点
  function setPendingAnchor(anchor: ZoomAnchor | null): void {
    pendingAnchor.value = anchor
  }

  return {
    isZooming,
    pendingAnchor,
    captureCenterAnchor,
    restoreAnchor,
    applyInterimScale,
    setZooming,
    setPendingAnchor
  }
}

export type ZoomManager = ReturnType<typeof useZoom>
