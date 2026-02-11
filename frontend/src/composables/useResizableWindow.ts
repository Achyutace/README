/*
----------------------------------------------------------------------
                              可放缩窗口
----------------------------------------------------------------------
*/ 
import { ref, onUnmounted } from 'vue'
import { clamp } from '@vueuse/core'

// 默认窗口尺寸限制
export const RESIZE_DEFAULTS = {
  MIN_WIDTH: 200,
  MAX_WIDTH: 800,
  MIN_HEIGHT: 150,
  MAX_HEIGHT: 600
}

// 定义尺寸类型
export interface Size {
  width: number
  height: number
}

// 放缩事件
export interface ResizeEvent {
  size: Size // 尺寸
  delta: { x: number; y: number } // 位置偏移量
}

// 放缩相关选项
export interface ResizeOptions {
  initialSize?: Size // 初始尺寸
  minWidth?: number // 最小宽度
  minHeight?: number // 最小高度
  maxWidth?: number // 最大宽度
  maxHeight?: number // 最大高度

  // 回调函数，可以由外部组件传入，在放缩不同阶段调用
  onResizeStart?: () => void // 放缩开始
  onResize?: (event: ResizeEvent) => void // 放缩中
  onResizeEnd?: (finalSize: Size) => void // 放缩结束
}

// 可放缩窗口的定义
export function useResizableWindow(options: ResizeOptions = {}) {
  // 初始化尺寸，若没有传入则默认为 300x200
  const size = ref<Size>(options.initialSize || { width: 300, height: 200 })

  const isResizing = ref(false) // 是否正在放缩，初始化为 false
  const activeDirection = ref('') // 当前放缩方向，初始化为空字符串
  
  const startMouse = ref({ x: 0, y: 0 }) // 放缩开始时的鼠标位置
  const startSize = ref({ width: 0, height: 0 }) // 放缩开始时的窗口尺寸

  // 开始放缩：记录状态和初始值，调用回调函数，添加全局鼠标事件监听
  function startResize(e: MouseEvent, direction: string) {
    e.preventDefault() // 阻止浏览器默认行为
    e.stopPropagation() // 阻止事件冒泡（向上传递）
    
    isResizing.value = true // 标记为正在放缩
    activeDirection.value = direction // 记录放缩方向
    startMouse.value = { x: e.clientX, y: e.clientY } // 记录放缩开始时的鼠标位置
    startSize.value = { ...size.value } // 记录放缩开始时的窗口尺寸

    options.onResizeStart?.() // 调用放缩开始的回调函数

    // 添加全局鼠标事件监听
    window.addEventListener('mousemove', onResize)
    window.addEventListener('mouseup', stopResize)
  }

  // 放缩中：计算新尺寸，应用边界约束，更新状态，调用回调函数
  function onResize(e: MouseEvent) {
    if (!isResizing.value) return // 确保正在放缩

    // 计算鼠标移动的距离
    const mouseDeltaX = e.clientX - startMouse.value.x
    const mouseDeltaY = e.clientY - startMouse.value.y
    
    // 初始化新尺寸和偏移量
    let newWidth = startSize.value.width
    let newHeight = startSize.value.height
    let shiftX = 0
    let shiftY = 0

    // 放缩方向
    const dir = activeDirection.value

    // 窗口尺寸限制，如果未定义则用默认设置
    const minW = options.minWidth ?? RESIZE_DEFAULTS.MIN_WIDTH
    const maxW = options.maxWidth ?? RESIZE_DEFAULTS.MAX_WIDTH
    const minH = options.minHeight ?? RESIZE_DEFAULTS.MIN_HEIGHT
    const maxH = options.maxHeight ?? RESIZE_DEFAULTS.MAX_HEIGHT

    // 水平方向
    if (dir.includes('e')) {
      // 向右放缩，增加宽度，不改变左边界
      newWidth = clamp(startSize.value.width + mouseDeltaX, minW, maxW)
    } 
    else if (dir.includes('w')) {
      // 向右放缩，增加宽度（此时 mouseDeltaX 为负），改变左边界
      newWidth = clamp(startSize.value.width - mouseDeltaX, minW, maxW)
      shiftX = -(newWidth - startSize.value.width)
    }

    // 垂直方向
    if (dir.includes('s')) {
      // 向下放缩，增加高度，不改变上边界
      newHeight = clamp(startSize.value.height + mouseDeltaY, minH, maxH)
    } else if (dir.includes('n')) {
      // 向下放缩，增加高度（此时 mouseDeltaY 为负），改变上边界
      newHeight = clamp(startSize.value.height - mouseDeltaY, minH, maxH)
      shiftY = -(newHeight - startSize.value.height)
    }

    // 更新尺寸状态
    size.value = { width: newWidth, height: newHeight }

    // 调用放缩中的回调函数，传入当前尺寸和偏移量
    options.onResize?.({ 
      size: size.value, 
      delta: { x: shiftX, y: shiftY } 
    })
  }

  // 停止放缩：重置状态，调用回调函数，移除全局鼠标事件监听
  function stopResize() {
    if (isResizing.value) {
      isResizing.value = false // 标记为不再放缩
      activeDirection.value = '' // 重置放缩方向
      options.onResizeEnd?.(size.value) // 调用放缩结束的回调函数，传入最终尺寸
    }

    // 移除全局鼠标事件监听
    window.removeEventListener('mousemove', onResize)
    window.removeEventListener('mouseup', stopResize)
  }

  // 直接设置尺寸
  function setSize(newSize: Size) {
    size.value = newSize
  }

  // 组件卸载时清理事件监听，防止内存泄漏
  onUnmounted(() => {
    window.removeEventListener('mousemove', onResize)
    window.removeEventListener('mouseup', stopResize)
  })

  return {
    size,
    isResizing,
    activeDirection,
    startResize,
    setSize
  }
}
