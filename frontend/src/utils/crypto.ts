/**
 * --------------------------------------------------------------------------------
 * Web Crypto API 安全工具类
 * 
 * 功能：利用浏览器原生的 window.crypto.subtle 提供高强度的本地数据加密。
 * 针对如 API Key 等敏感信息，通过输入用户自定义 PIN 码派生出 AES-GCM 密钥，
 * 确保数据以密文形式存储于 localStorage，抵御一般的 XSS 拖库攻击。
 * --------------------------------------------------------------------------------
 */

// 将字符串转为 ArrayBuffer
function str2ab(str: string): ArrayBuffer {
    return new TextEncoder().encode(str).buffer
}

// 将 ArrayBuffer 转为十六进制字符串 (方便存储)
function buf2hex(buffer: ArrayBuffer): string {
    return Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('')
}

// 将十六进制字符串转为 ArrayBuffer
function hex2buf(hex: string): ArrayBuffer {
    const bytes = new Uint8Array(Math.ceil(hex.length / 2))
    for (let i = 0; i < bytes.length; i++) {
        bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16)
    }
    return bytes.buffer
}

/**
 * 派生密钥：使用用户的 PIN 码和指定的盐 (Salt) 通过 PBKDF2 算法派生出一个 AES-GCM 密钥。
 * @param pin 用户输入的 PIN 码
 * @param salt 盐 (应确保唯一性，例如一个固定的项目级短语或随机字符串)
 */
export async function deriveKeyFromPin(pin: string, salt: string = 'readme-fusion-salt'): Promise<CryptoKey> {
    // 第一步：把用户明文 PIN 当作底层材料
    const keyMaterial = await window.crypto.subtle.importKey(
        'raw',
        str2ab(pin),
        { name: 'PBKDF2' },
        false,
        ['deriveBits', 'deriveKey']
    )

    // 第二步：通过 100000 次哈希迭代，生成 256位 AES 密钥
    return window.crypto.subtle.deriveKey(
        {
            name: 'PBKDF2',
            salt: str2ab(salt),
            iterations: 100000,
            hash: 'SHA-256'
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
    )
}

/**
 * 加密数据
 * @param plaintext 明文字符串 (如 JSON.stringify 后的数据)
 * @param key 用 deriveKeyFromPin 获取到的 AES 密钥
 * @returns 密文 (Hex) 以及本次加密使用的初始向量 IV (Hex)
 */
export async function encryptData(plaintext: string, key: CryptoKey): Promise<{ cipher: string, iv: string }> {
    // 必须的 IV，AES-GCM 每次加密要求唯一，随机生成 12 字节
    const iv = window.crypto.getRandomValues(new Uint8Array(12))

    const encryptedBuf = await window.crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        str2ab(plaintext)
    )

    return {
        cipher: buf2hex(encryptedBuf),
        iv: buf2hex(iv.buffer)
    }
}

/**
 * 解密数据
 * @param cipherHex 密文 (Hex)
 * @param ivHex 加密时使用的 IV (Hex)
 * @param key 用 deriveKeyFromPin 获取到的 AES 密钥
 * @returns 解密后的明文
 */
export async function decryptData(cipherHex: string, ivHex: string, key: CryptoKey): Promise<string> {
    try {
        const decryptedBuf = await window.crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: hex2buf(ivHex) },
            key,
            hex2buf(cipherHex)
        )
        return new TextDecoder().decode(decryptedBuf)
    } catch (error) {
        throw new Error('解密失败，可能是 PIN 码错误或数据被篡改')
    }
}
