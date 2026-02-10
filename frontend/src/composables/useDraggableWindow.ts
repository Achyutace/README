/*
----------------------------------------------------------------------
                              可拖动窗口
----------------------------------------------------------------------
*/ 
import { ref, onUnmounted } from 'vue'

// 定义位置类型
export interface Position {
  x: number
  y: number
}

// 拖动相关选项
export interface DragOptions {
  initialPosition?: Position    // 初始位置
  boundary?: HTMLElement | Window    // 拖动边界元素，默认为 window

  // 回调函数，可以由外部组件传入，在拖动不同阶段调用
  onDragStart?: () => void    // 拖动开始
  onDrag?: (pos: Position) => void    // 拖动中
  onDragEnd?: (finalPos: Position) => void    // 拖动结束
}

// 可拖动窗口的定义
export function useDraggableWindow(options: DragOptions = {}) {
  // 初始化坐标
  const position = ref<Position>(options.initialPosition || { x: 0, y: 0 })

  // 初始化拖动状态为 false
  const isDragging = ref(false)

  // 初始化拖动偏移量为 (0, 0)
  const dragOffset = ref({ x: 0, y: 0 })

  // 开始拖动
  function startDrag(e: MouseEvent) {
    if (e.button !== 0) return // 只响应左键拖动
    
    e.preventDefault() // 阻止浏览器默认行为
    isDragging.value = true // 标记为正在拖动
    
    // 计算鼠标相对窗口位置：鼠标位置与窗口位置的差值
    dragOffset.value = {
      x: e.clientX - position.value.x,
      y: e.clientY - position.value.y
    }

    // 调用拖动开始的回调函数
    options.onDragStart?.()
    
    // 添加全局鼠标事件监听
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
  }

  // 拖动中：计算新位置，应用边界约束，更新状态
  function onDrag(e: MouseEvent) {
    if (!isDragging.value) return // 确保正在拖动

    // 计算窗口新位置：鼠标新位置减去鼠标相对窗口位置
    let newX = e.clientX - dragOffset.value.x
    let newY = e.clientY - dragOffset.value.y

    // 应用边界约束，如果边界是 window，则限制在屏幕范围内
    if (options.boundary === window) {
       const maxX = window.innerWidth
       const maxY = window.innerHeight

       newX = Math.max(-100, Math.min(newX, maxX - 50))
       newY = Math.max(0, Math.min(newY, maxY - 50))
    }

    // 更新位置状态
    position.value = { x: newX, y: newY }

    // 调用拖动中的回调函数
    options.onDrag?.(position.value)
  }

  // 停止拖动：更新状态，调用回调函数，移除全局鼠标事件监听
  function stopDrag() {
    // 如果正在拖动，标记为不再拖动，并调用拖动结束的回调函数
    if (isDragging.value) {
      isDragging.value = false // 标记为不再拖动
      options.onDragEnd?.(position.value) // 调用拖动结束的回调函数
    }

    // 移除全局鼠标事件监听
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  }

  // 外部接口：提供直接设置位置的方法
  function setPosition(pos: Position) {
    position.value = pos
  }

  // 组件卸载时清理事件监听，防止内存泄漏
  onUnmounted(() => {
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  })

  return {
    position,
    isDragging,
    startDrag,
    setPosition
  }
}
