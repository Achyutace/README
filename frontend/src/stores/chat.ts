import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ChatMessage } from '../types'
import { chatSessionApi } from '../api'
import { dbPut, dbPutMany, dbGetAll, dbClear, dbGet, dbDelete, STORES } from '../utils/db'

export interface ChatSession {
    id: string
    pdfId: string
    title: string
    messages: ChatMessage[]
    createdAt: string
    updatedAt: string
}

export const useChatStore = defineStore('chat', () => {
    const chatMessages = ref<ChatMessage[]>([])
    const currentSessionId = ref<string | null>(localStorage.getItem('readme_current_session') || null)
    const chatSessions = ref<ChatSession[]>([])
    const isLoadingChat = ref(false)

    watch(currentSessionId, (newId) => {
        if (newId) {
            localStorage.setItem('readme_current_session', newId)
        } else {
            localStorage.removeItem('readme_current_session')
        }
    })

    async function hydrateFromDB() {
        try {
            const records = await dbGetAll<Omit<ChatSession, 'messages'>>(STORES.CHAT_SESSIONS)
            if (records.length > 0) {
                chatSessions.value = records
                    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
                    .map(rec => ({ ...rec, messages: [] }))
                console.log(`[Chat Store] Hydrated ${records.length} sessions from IndexedDB`)
            }
        } catch (error) {
            console.warn('[Chat Store] Failed to hydrate sessions from IndexedDB:', error)
        }
    }

    // 初始化时已通过 store 导出外的生命周期或组件挂载处理，避免双重水合

    async function loadSessionsFromBackend(pdfId?: string) {
        try {
            const response = await chatSessionApi.listSessions(pdfId)
            if (response.success && response.sessions) {
                const backendSessions = response.sessions.map(s => ({
                    id: s.id,
                    pdfId: s.pdfId || '',
                    title: s.title,
                    messages: [] as ChatMessage[],
                    createdAt: s.createdAt,
                    updatedAt: s.updatedAt
                }))

                if (pdfId) {
                    const otherSessions = chatSessions.value.filter(s => s.pdfId !== pdfId || s.id.startsWith('temp_'))
                    chatSessions.value = [...backendSessions, ...otherSessions]
                } else {
                    const tempSessions = chatSessions.value.filter(s => s.id.startsWith('temp_'))
                    chatSessions.value = [...backendSessions, ...tempSessions]
                }

                if (currentSessionId.value && !currentSessionId.value.startsWith('temp_')) {
                    const stillExists = chatSessions.value.some(s => s.id === currentSessionId.value)
                    if (!stillExists) {
                        console.warn(`[Chat Store] Session ${currentSessionId.value} no longer exists on backend. Resetting.`)
                        clearChat()
                    }
                }

                await dbClear(STORES.CHAT_SESSIONS)
                if (chatSessions.value.length > 0) {
                    await dbPutMany(STORES.CHAT_SESSIONS, chatSessions.value.map(s => ({ ...s, messages: [] })))
                }

                console.log(`Loaded ${response.sessions.length} sessions from backend for pdfId: ${pdfId || 'all'}`)
            }
        } catch (error) {
            console.error('Failed to load sessions from backend:', error)
        }
    }

    async function loadSessionMessagesFromBackend(sessionId: string) {
        try {
            const response = await chatSessionApi.getSessionMessages(sessionId)
            if (response.success && response.messages) {
                const messages: ChatMessage[] = response.messages.map(m => ({
                    id: String(m.id),
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                    timestamp: new Date(m.created_time),
                    citations: m.citations || []
                }))

                const session = chatSessions.value.find(s => s.id === sessionId)
                if (session) {
                    session.messages = messages
                }

                if (currentSessionId.value === sessionId) {
                    chatMessages.value = messages
                }

                if (messages.length > 0) {
                    dbPut(STORES.CHAT_MESSAGES, { id: sessionId, messages }).catch(err => {
                        console.warn('[Chat Store] Failed to save messages to IndexedDB', err)
                    })
                }

                console.log(`Loaded ${messages.length} messages for session: ${sessionId}`)
                return messages
            }
        } catch (error) {
            console.error('Failed to load session messages from backend:', error)
        }
        return []
    }

    function addChatMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
        const newMessage = {
            ...message,
            id: crypto.randomUUID(),
            timestamp: new Date(),
        }
        chatMessages.value.push(newMessage)

        if (currentSessionId.value) {
            const session = chatSessions.value.find(s => s.id === currentSessionId.value)
            if (session) {
                session.messages = [...chatMessages.value]
                session.updatedAt = new Date().toISOString()
                if (!session.title || session.title === '新对话') {
                    const firstUserMsg = session.messages.find(m => m.role === 'user')
                    if (firstUserMsg) {
                        session.title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '')
                    }
                }

                if (!session.id.startsWith('temp_')) {
                    dbPut(STORES.CHAT_SESSIONS, { ...session, messages: [] }).catch(e => console.warn(e))
                    dbPut(STORES.CHAT_MESSAGES, { id: session.id, messages: session.messages }).catch(e => console.warn(e))
                }
            }
        }
    }

    function copySelectedAsJson(selectedMessageIds: Set<string>) {
        const selected = chatMessages.value.filter(m => selectedMessageIds.has(m.id))
        const list = selected.map(m => ({
            role: m.role === 'user' ? '用户' : 'AI',
            content: m.content,
            timestamp: m.timestamp
        }))
        return JSON.stringify(list, null, 2)
    }

    function getHistoryBeforeIndex(index: number): Array<{ role: string; content: string }> {
        return chatMessages.value.slice(0, index).map(m => ({
            role: m.role,
            content: m.content
        }))
    }

    function clearChat() {
        chatMessages.value = []
        currentSessionId.value = null
    }

    async function createNewSession(pdfId: string): Promise<string> {
        // 防止连续创建多个空会话，并修复之前误匹配到后端发回的真实空会话 bug
        const existingTemp = chatSessions.value.find(s => s.pdfId === pdfId && s.id.startsWith('temp_'))
        if (existingTemp) {
            currentSessionId.value = existingTemp.id
            chatMessages.value = existingTemp.messages || []
            return existingTemp.id
        }

        const tempId = `temp_${Date.now()}_${crypto.randomUUID()}`
        const newSession: ChatSession = {
            id: tempId,
            pdfId,
            title: '新对话',
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        }

        chatSessions.value.unshift(newSession)
        currentSessionId.value = tempId
        chatMessages.value = []

        return tempId
    }

    async function ensureRealSession(pdfId: string): Promise<string> {
        if (!currentSessionId.value || currentSessionId.value.startsWith('temp_')) {
            const tempId = currentSessionId.value;
            const data = await chatSessionApi.createSession();
            // @ts-ignore
            if (!data.sessionId) {
                throw new Error('Failed to create real session from backend');
            }
            // @ts-ignore
            const realId = data.sessionId;

            if (tempId) {
                const sessionIndex = chatSessions.value.findIndex(s => s.id === tempId);
                if (sessionIndex !== -1) {
                    const session = chatSessions.value[sessionIndex] as ChatSession;
                    session.id = realId;
                    // @ts-ignore
                    session.title = data.title || session.title || '新对话';

                    dbDelete(STORES.CHAT_SESSIONS, tempId).catch(e => console.warn(e));
                    dbDelete(STORES.CHAT_MESSAGES, tempId).catch(e => console.warn(e));

                    dbPut(STORES.CHAT_SESSIONS, { ...session, messages: [] }).catch(e => console.warn(e));
                    dbPut(STORES.CHAT_MESSAGES, { id: realId, messages: chatMessages.value as ChatMessage[] }).catch(e => console.warn(e));
                }
            } else {
                const newSession: ChatSession = {
                    id: realId,
                    pdfId,
                    // @ts-ignore
                    title: data.title || '新对话',
                    messages: [],
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString()
                }
                chatSessions.value.unshift(newSession)
            }

            currentSessionId.value = realId;

            import('../utils/broadcast').then(({ broadcastSync }) => {
                broadcastSync('RELOAD_SESSIONS', pdfId)
            })

            return realId;
        }
        return currentSessionId.value;
    }

    async function loadSession(sessionId: string) {
        const session = chatSessions.value.find(s => s.id === sessionId)
        if (session) {
            currentSessionId.value = sessionId

            if (session.messages.length === 0) {
                isLoadingChat.value = true
                try {
                    const cached = await dbGet<{ id: string, messages: ChatMessage[] }>(STORES.CHAT_MESSAGES, sessionId)
                    if (cached && cached.messages && cached.messages.length > 0) {
                        session.messages = cached.messages
                        if (currentSessionId.value === sessionId) {
                            chatMessages.value = [...session.messages]
                        }
                        console.log(`[Chat Store] Loaded ${cached.messages.length} messages from IndexedDB for session: ${sessionId}`)
                    } else {
                        await loadSessionMessagesFromBackend(sessionId)
                    }
                } finally {
                    isLoadingChat.value = false
                }
            } else {
                chatMessages.value = [...session.messages]
            }
        } else {
            console.warn(`[Chat Store] Session ${sessionId} not found in local cache. Clearing stale session ID.`)
            currentSessionId.value = null
            chatMessages.value = []
        }
    }

    function getSessionsByPdfId(pdfId: string): ChatSession[] {
        return chatSessions.value.filter(s => s.pdfId === pdfId && !s.id.startsWith('temp_'))
    }

    async function deleteSession(sessionId: string) {
        try {
            const response = await chatSessionApi.deleteSession(sessionId)

            if (response.success) {
                const index = chatSessions.value.findIndex(s => s.id === sessionId)
                const sessionToRemove = chatSessions.value[index]
                if (index !== -1 && sessionToRemove) {
                    const pdfId = sessionToRemove.pdfId
                    chatSessions.value.splice(index, 1)
                    if (currentSessionId.value === sessionId) {
                        clearChat()
                    }

                    dbDelete(STORES.CHAT_SESSIONS, sessionId).catch(e => console.warn(e))
                    dbDelete(STORES.CHAT_MESSAGES, sessionId).catch(e => console.warn(e))

                    import('../utils/broadcast').then(({ broadcastSync }) => {
                        broadcastSync('RELOAD_SESSIONS', pdfId)
                    })
                }
                console.log(`Session ${sessionId} deleted. ${response.deletedMessages} messages removed.`)
            }
        } catch (error: any) {
            console.error('Failed to delete session:', error)
            throw error
        }
    }

    function resetForNewDocument() {
        chatMessages.value = []
        currentSessionId.value = null
    }

    function clearAllData() {
        chatMessages.value = []
        chatSessions.value = []
        currentSessionId.value = null
        localStorage.removeItem('readme_current_session')

        dbClear(STORES.CHAT_SESSIONS).catch(e => console.warn(e))
        dbClear(STORES.CHAT_MESSAGES).catch(e => console.warn(e))
    }

    import('../utils/broadcast').then(({ syncChannel }) => {
        syncChannel.addEventListener('message', (event) => {
            const { type, payload } = event.data

            switch (type) {
                case 'RELOAD_SESSIONS':
                    if (payload) {
                        loadSessionsFromBackend(payload)
                    } else {
                        loadSessionsFromBackend()
                    }
                    break
                case 'RELOAD_MESSAGES':
                    if (payload && payload === currentSessionId.value) {
                        loadSessionMessagesFromBackend(payload)
                    }
                    break
            }
        })
    }).catch(e => console.error("Broadcast init failed in Chat store", e))

    return {
        chatMessages,
        currentSessionId,
        chatSessions,
        isLoadingChat,
        hydrateFromDB,
        addChatMessage,
        clearChat,
        createNewSession,
        ensureRealSession,
        loadSession,
        loadSessionsFromBackend,
        loadSessionMessagesFromBackend,
        getSessionsByPdfId,
        deleteSession,
        copySelectedAsJson,
        getHistoryBeforeIndex,
        resetForNewDocument,
        clearAllData,
    }
})
