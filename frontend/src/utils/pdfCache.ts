/**
 * PDF 文件 IndexedDB 本地缓存管理
 */

const DB_NAME = 'readme_pdf_cache'
const DB_VERSION = 1
const STORE_NAME = 'pdfs'

/**
 * 初始化并打开 IndexedDB
 */
function openDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION)

        request.onerror = () => {
            console.error('Failed to open IndexedDB:', request.error)
            reject(request.error)
        }

        request.onsuccess = () => {
            resolve(request.result)
        }

        request.onupgradeneeded = (event) => {
            const db = (event.target as IDBOpenDBRequest).result
            // 创建一个对象仓库，主键为 id
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id' })
            }
        }
    })
}

/**
 * 保存 PDF Blob 到缓存
 * @param id PDF 文档的唯一 ID
 * @param blob PDF 的二进制文件流
 */
export async function savePdfToCache(id: string, blob: Blob): Promise<void> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_NAME, 'readwrite')
            const store = transaction.objectStore(STORE_NAME)

            const request = store.put({ id, blob })

            request.onsuccess = () => resolve()
            request.onerror = () => {
                console.error(`Failed to cache PDF ${id}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn('IndexedDB not available or failed to open', error)
    }
}

/**
 * 从缓存中获取 PDF Blob
 * @param id PDF 文档的唯一 ID
 * @returns PDF 的 Blob，如果不存在则返回 null
 */
export async function getPdfFromCache(id: string): Promise<Blob | null> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_NAME, 'readonly')
            const store = transaction.objectStore(STORE_NAME)

            const request = store.get(id)

            request.onsuccess = () => {
                if (request.result && request.result.blob) {
                    resolve(request.result.blob)
                } else {
                    resolve(null)
                }
            }

            request.onerror = () => {
                console.error(`Failed to get cached PDF ${id}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn('IndexedDB not available or failed to open', error)
        return null
    }
}

/**
 * 从缓存中删除特定的 PDF Blob
 * @param id PDF 文档的唯一 ID
 */
export async function removePdfFromCache(id: string): Promise<void> {
    try {
        const db = await openDB()
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_NAME, 'readwrite')
            const store = transaction.objectStore(STORE_NAME)

            const request = store.delete(id)

            request.onsuccess = () => resolve()
            request.onerror = () => {
                console.error(`Failed to clean cached PDF ${id}:`, request.error)
                reject(request.error)
            }
        })
    } catch (error) {
        console.warn('IndexedDB not available or failed to open', error)
    }
}
