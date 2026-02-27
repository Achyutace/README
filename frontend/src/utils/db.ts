/**
 * ============================================================================
 * 统一 IndexedDB 管理器
 *
 * 功能：为整个前端应用提供统一的 IndexedDB 读写接口。
 * 所有需要 IndexedDB 持久化的模块（PDF 缓存、文献库、翻译缓存、聊天会话等）
 * 均通过此管理器进行操作，避免各模块各自维护数据库连接。
 *
 * 设计要点：
 * - 单例模式：全局共用一个 IDBDatabase 实例
 * - 统一版本管理：所有 object store 在同一个数据库中
 * - 所有记录自动附加 cachedAt 时间戳，用于定时过期清除
 * ============================================================================
 */

const DB_NAME = 'readme_app_db'
const DB_VERSION = 2 // 从 v1 (仅 pdfs) 升级到 v2 (全量 store)

/**
 * 所有 Object Store 的名称常量
 */
export const STORES = {
    PDFS: 'pdfs',                   // PDF Blob 缓存
    LIBRARY: 'library',             // 文献元数据
    TRANSLATIONS: 'translations',   // 翻译段落对
    CHAT_SESSIONS: 'chat_sessions', // 聊天会话元数据
    CHAT_MESSAGES: 'chat_messages', // 聊天消息 (key = sessionId)
} as const

type StoreName = (typeof STORES)[keyof typeof STORES]

// 单例数据库实例
let dbInstance: IDBDatabase | null = null

/**
 * 打开（或获取已打开的）IndexedDB 数据库实例
 */
function openDB(): Promise<IDBDatabase> {
    if (dbInstance) return Promise.resolve(dbInstance)

    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION)

        request.onerror = () => {
            console.error('[DB] Failed to open IndexedDB:', request.error)
            reject(request.error)
        }

        request.onsuccess = () => {
            dbInstance = request.result

            // 当数据库连接意外关闭时，清除单例引用
            dbInstance.onclose = () => {
                dbInstance = null
            }

            resolve(dbInstance)
        }

        request.onupgradeneeded = (event) => {
            const db = (event.target as IDBOpenDBRequest).result

            // 创建所有需要的 object store
            for (const storeName of Object.values(STORES)) {
                if (!db.objectStoreNames.contains(storeName)) {
                    db.createObjectStore(storeName, { keyPath: 'id' })
                }
            }
        }
    })
}

// ======================== 通用 CRUD 操作 ========================

/**
 * 存入数据（插入或更新）
 * 自动添加 cachedAt 时间戳
 */
export async function dbPut<T extends { id: string }>(storeName: StoreName, data: T): Promise<void> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite')
            const store = tx.objectStore(storeName)
            const record = { ...data, cachedAt: Date.now() }
            const request = store.put(record)
            request.onsuccess = () => resolve()
            request.onerror = () => {
                console.error(`[DB] put failed for ${storeName}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
    }
}

/**
 * 批量存入数据
 */
export async function dbPutMany<T extends { id: string }>(storeName: StoreName, items: T[]): Promise<void> {
    if (items.length === 0) return
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite')
            const store = tx.objectStore(storeName)
            const now = Date.now()
            for (const item of items) {
                store.put({ ...item, cachedAt: now })
            }
            tx.oncomplete = () => resolve()
            tx.onerror = () => {
                console.error(`[DB] putMany failed for ${storeName}:`, tx.error)
                reject(tx.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
    }
}

/**
 * 读取单条数据
 */
export async function dbGet<T = any>(storeName: StoreName, key: string): Promise<T | null> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly')
            const store = tx.objectStore(storeName)
            const request = store.get(key)
            request.onsuccess = () => {
                resolve(request.result ?? null)
            }
            request.onerror = () => {
                console.error(`[DB] get failed for ${storeName}/${key}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
        return null
    }
}

/**
 * 读取 store 中的所有数据
 */
export async function dbGetAll<T = any>(storeName: StoreName): Promise<T[]> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly')
            const store = tx.objectStore(storeName)
            const request = store.getAll()
            request.onsuccess = () => {
                resolve(request.result ?? [])
            }
            request.onerror = () => {
                console.error(`[DB] getAll failed for ${storeName}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
        return []
    }
}

/**
 * 删除单条数据
 */
export async function dbDelete(storeName: StoreName, key: string): Promise<void> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite')
            const store = tx.objectStore(storeName)
            const request = store.delete(key)
            request.onsuccess = () => resolve()
            request.onerror = () => {
                console.error(`[DB] delete failed for ${storeName}/${key}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
    }
}

/**
 * 清空整个 object store
 */
export async function dbClear(storeName: StoreName): Promise<void> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite')
            const store = tx.objectStore(storeName)
            const request = store.clear()
            request.onsuccess = () => resolve()
            request.onerror = () => {
                console.error(`[DB] clear failed for ${storeName}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
    }
}

// ======================== 过期清除 ========================

/**
 * 清除指定 store 中超过 maxAgeMs 毫秒的过期记录
 * @param storeName  目标 store 名
 * @param maxAgeMs   最大存活时间（毫秒）
 * @returns 被清除的记录数
 */
export async function dbCleanExpired(storeName: StoreName, maxAgeMs: number): Promise<number> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite')
            const store = tx.objectStore(storeName)
            const request = store.getAll()
            let deletedCount = 0

            request.onsuccess = () => {
                const now = Date.now()
                const records = request.result || []
                for (const record of records) {
                    if (record.cachedAt && (now - record.cachedAt) > maxAgeMs) {
                        store.delete(record.id)
                        deletedCount++
                    }
                }
            }

            tx.oncomplete = () => {
                if (deletedCount > 0) {
                    console.log(`[DB] Cleaned ${deletedCount} expired records from ${storeName}`)
                }
                resolve(deletedCount)
            }

            tx.onerror = () => {
                console.error(`[DB] cleanExpired failed for ${storeName}:`, tx.error)
                reject(tx.error)
            }
        })
    } catch (error) {
        console.warn(`[DB] IndexedDB not available for ${storeName}`, error)
        return 0
    }
}
