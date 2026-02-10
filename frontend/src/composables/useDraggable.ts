/*
----------------------------------------------------------------------
                              文字划线
----------------------------------------------------------------------
*/ 
import { reactive, onUnmounted } from 'vue'

// 划线状态接口
export function useDraggable() {
  const dragState = reactive({
    isDragging: false, // 是否正在拖动
    startX: 0, // 拖动起始X坐标
    startY: 0, // 拖动起始Y坐标
    offsetX: 0, // 当前X偏移量
    offsetY: 0, // 当前Y偏移量
    prevOffsetX: 0, // 上一次拖动结束时的X偏移量
    prevOffsetY: 0 // 上一次拖动结束时的Y偏移量
  })

  // 开始拖动：初始化状态，添加全局鼠标事件监听
  function startDrag(event: MouseEvent) {
    event.preventDefault()
    dragState.isDragging = true
    dragState.startX = event.clientX
    dragState.startY = event.clientY
    dragState.prevOffsetX = dragState.offsetX
    dragState.prevOffsetY = dragState.offsetY
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
  }

  // 拖动中：计算偏移量，更新状态
  function onDrag(event: MouseEvent) {
    if (!dragState.isDragging) return // 如果不在拖动状态，直接返回
    const deltaX = event.clientX - dragState.startX 
    const deltaY = event.clientY - dragState.startY 
    dragState.offsetX = dragState.prevOffsetX + deltaX
    dragState.offsetY = dragState.prevOffsetY + deltaY
  }

  // 停止拖动：移除全局鼠标事件监听，更新状态
  function stopDrag() {
    dragState.isDragging = false // 标记为不再拖动
    window.removeEventListener('mousemove', onDrag) // 移除鼠标移动监听
    window.removeEventListener('mouseup', stopDrag) // 移除鼠标释放监听
  }

  // 重置拖动状态
  function resetDrag() {
    dragState.offsetX = 0
    dragState.offsetY = 0
    dragState.prevOffsetX = 0
    dragState.prevOffsetY = 0
  }

  onUnmounted(() => {
    window.removeEventListener('mousemove', onDrag)
    window.removeEventListener('mouseup', stopDrag)
  })

  return {
    dragState,
    startDrag,
    resetDrag
  }
}
