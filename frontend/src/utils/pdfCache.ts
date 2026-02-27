/**
 * PDF 文件 IndexedDB 本地缓存管理
 *
 * 基于统一 DB 管理器（db.ts）实现。
 * 保持导出接口不变，内部调用 dbPut / dbGet / dbDelete。
 */

import { dbPut, dbGet, dbDelete, dbCleanExpired, STORES } from './db'

/** PDF 缓存记录的内部结构 */
interface PdfCacheRecord {
    id: string
    blob: Blob
    cachedAt?: number
}

/** PDF 缓存默认过期时间：7 天 */
const PDF_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

/**
 * 保存 PDF Blob 到缓存
 * @param id PDF 文档的唯一 ID
 * @param blob PDF 的二进制文件流
 */
export async function savePdfToCache(id: string, blob: Blob): Promise<void> {
    await dbPut(STORES.PDFS, { id, blob })
}

/**
 * 从缓存中获取 PDF Blob
 * @param id PDF 文档的唯一 ID
 * @returns PDF 的 Blob，如果不存在则返回 null
 */
export async function getPdfFromCache(id: string): Promise<Blob | null> {
    const record = await dbGet<PdfCacheRecord>(STORES.PDFS, id)
    return record?.blob ?? null
}

/**
 * 从缓存中删除特定的 PDF Blob
 * @param id PDF 文档的唯一 ID
 */
export async function removePdfFromCache(id: string): Promise<void> {
    await dbDelete(STORES.PDFS, id)
}

/**
 * 清除过期的 PDF 缓存（超过 7 天的记录）
 * 建议在应用启动时调用一次
 */
export async function cleanExpiredPdfCache(): Promise<number> {
    return dbCleanExpired(STORES.PDFS, PDF_MAX_AGE_MS)
}
