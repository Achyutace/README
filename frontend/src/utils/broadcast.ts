/**
 * 跨标签页通信频道实例
 * 
 * 用于在应用的不同标签页之间广播状态更新事件。
 * 例如：当在 A 标签页进行高亮、更新了自定义模型或创建了新会话时，
 * 通过该频道通知 B 标签页，使其自动重新拉取后端数据，实现“信息及时更新”。
 */

// 通道名称
const CHANNEL_NAME = 'readme_sync_channel'

export const syncChannel = new BroadcastChannel(CHANNEL_NAME)

// 支持的同步事件类型
export type SyncEventType =
    | 'RELOAD_SESSIONS'      // 重新加载会话列表 (包含新建/删除会话)
    | 'RELOAD_MESSAGES'      // 重新加载当前会话消息
    | 'RELOAD_HIGHLIGHTS'    // 重新加载当前 PDF 的高亮
    | 'RELOAD_CUSTOM_MODELS' // 重新加载自定义模型列表

export interface SyncMessage {
    type: SyncEventType
    payload?: any // 可选携带附加信息，例如被操作的 pdfId 或 sessionId
}

/**
 * 发送同步广播
 */
export function broadcastSync(type: SyncEventType, payload?: any) {
    syncChannel.postMessage({ type, payload })
}
