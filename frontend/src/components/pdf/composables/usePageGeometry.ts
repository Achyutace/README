/**
 * 页面几何计算 Composable
 * 处理页面尺寸、位置计算、查找等
 */

import { ref, type Ref } from 'vue'
import type { PageSize } from '../types/pdf'
import { PAGE_GAP, CONTAINER_PADDING } from '../utils/pdfHelpers'

export type PageGeometry = ReturnType<typeof usePageGeometry>

export function usePageGeometry(scale: Ref<number>) {
  // 页面尺寸预加载（用于快速滚动时的占位）
  // 优化：如果是常数（大部分论文），使用 pageSizesConstant；否则使用 pageSizesArray 并配合 accumulatedHeights 进行二分查找
  const pageSizesConstant = ref<PageSize | null>(null)
  const pageSizesArray = ref<PageSize[] | null>(null)
  const pageHeightAccumulator = ref<number[]>([]) // 前缀和数组，用于二分查找

  // 获取页面尺寸
  function getPageSize(pageNumber: number): PageSize {
    if (pageSizesConstant.value) {
      return pageSizesConstant.value
    }
    if (pageSizesArray.value) {
      return pageSizesArray.value[pageNumber - 1] ?? { width: 612, height: 792 }
    }
    return { width: 612, height: 792 }
  }

  // 获取指定页面的缩放后尺寸
  function getScaledPageSize(pageNumber: number): PageSize {
    const size = getPageSize(pageNumber) || { width: 612, height: 792 }

    return {
      width: Math.floor(size.width * scale.value),
      height: Math.floor(size.height * scale.value)
    }
  }

  // 获取页面顶部距离容器顶部的距离 (px)
  function getPageTop(pageNumber: number): number {
    const index = pageNumber - 1
    if (index < 0) return CONTAINER_PADDING

    const s = scale.value

    // 常数高度情况 - O(1)
    if (pageSizesConstant.value) {
      const h = pageSizesConstant.value.height * s
      // 保证计算出来的 top 为整数像素，避免缩放后累积的浮点误差
      return Math.round(CONTAINER_PADDING + index * (h + PAGE_GAP))
    }

    // 变长高度情况 - O(1) 查表
    if (pageHeightAccumulator.value.length > index) {
      const accH = pageHeightAccumulator.value[index] ?? 0
      // 同样对变长高度情况取整，保证逻辑上的页 top 与 DOM 中的 offsetTop 对齐
      return Math.round(CONTAINER_PADDING + accH * s + index * PAGE_GAP)
    }

    return CONTAINER_PADDING
  }

  // 根据垂直滚动位置查找页码
  function getPageAtY(y: number, pageCount: number): number {
    if (pageCount === 0) return 1

    const yAdjusted = y - CONTAINER_PADDING // Adjust for container padding

    if (yAdjusted < 0) return 1

    // 常数PDF高度情况 - 直接计算 O(1)
    if (pageSizesConstant.value) {
      const itemHeight = pageSizesConstant.value.height * scale.value + PAGE_GAP
      const index = Math.floor(yAdjusted / itemHeight)
      return Math.max(1, Math.min(pageCount, index + 1))
    }

    // 变长PDF高度情况 - 二分查找 O(log N)
    let low = 1, high = pageCount
    let result = 1
    while (low <= high) {
      const mid = Math.floor((low + high) / 2)
      const top = getPageTop(mid)

      if (y >= top) {
        result = mid
        low = mid + 1
      } else {
        high = mid - 1
      }
    }
    return result
  }

  // 设置页面尺寸数据
  function setPageSizes(sizes: PageSize[], allSameSize: boolean): void {
    if (allSameSize && sizes.length > 0) {
      pageSizesConstant.value = sizes[0] ?? null
      pageSizesArray.value = null
      pageHeightAccumulator.value = []
    } else {
      pageSizesConstant.value = null
      pageSizesArray.value = sizes

      // 计算前缀和
      const accumulator: number[] = [0]
      let currentAccHeight = 0
      for (let i = 0; i < sizes.length; i++) {
        const size = sizes[i]
        if (size) {
          currentAccHeight += size.height
        }
        if (i < sizes.length - 1) {
          accumulator.push(currentAccHeight)
        }
      }
      pageHeightAccumulator.value = accumulator
    }
  }

  // 清理
  function cleanup(): void {
    pageSizesConstant.value = null
    pageSizesArray.value = null
    pageHeightAccumulator.value = []
  }

  return {
    pageSizesConstant,
    pageSizesArray,
    pageHeightAccumulator,
    getPageSize,
    getScaledPageSize,
    getPageTop,
    getPageAtY,
    setPageSizes,
    cleanup
  }
}
