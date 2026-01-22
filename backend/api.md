# 后端 API 接口文档

## 1. 基础说明

*   **Base URL**: `http://localhost:5000/api` (默认本地开发地址)
*   **鉴权与用户隔离**:
    *   后端通过请求头 `X-User-Id` 或 URL 参数 `userId` 来区分不同用户的数据存储目录。
    *   建议在所有请求 Header 中携带 `X-User-Id`。
*   **跨域**: 已开启 CORS，允许所有来源访问 `/api/*`。

---

## 2. 系统检测

### 健康检查
检测后端服务及各组件（数据库、RAG、Agent等）的初始化状态。

- **接口**: `GET /health`
- **响应示例**:
```json
{
  "status": "ok",
  "user_id": "default_user",
  "services": {
    "storage": true,
    "rag": true,
    "translate": true,
    "agent": true,
    "chat": true
  }
}
```

## 3. PDF 文件管理 (`/api/pdf`)

### 上传 PDF
上传文件，计算 Hash，解析段落，响应给前端，并触发后台数据库存储和RAG索引构建。

- **接口**: `POST /pdf/upload`
- **Content-Type**: `multipart/form-data`
- **参数**:
    - `file`: (File) PDF 文件对象
- **响应**:
```json
{
  "id": "a1b2c3...",          // 文件 Hash，作为 pdfId
  "filename": "paper.pdf",
  "pageCount": 10,
  "fileHash": "a1b2c3...",
  "paragraphs": [...],        // 解析出的段落数据
  "status": "processing",     // 标识后台正在进行 RAG 索引
  "isNewUpload": true         // false 表示秒传（文件已存在）
}
```

### 获取 PDF 元数据
- **接口**: `GET /pdf/<pdf_id>/info`
- **响应**: PDF 的基本信息（文件名、页数、上传时间等）。

### 获取 PDF 纯文本
- **接口**: `GET /pdf/<pdf_id>/text`
- **Query 参数**:
    - `page`: (Int, 可选) 指定页码
- **响应**: 返回指定页或全文的文本内容。

---

## 4. 聊天对话 (`/api/chatbox`)

### 创建新会话
生成一个新的会话 ID，返回给前端。

- **接口**: `POST /chatbox/new`
- **响应**:
```json
{
  "sessionId": "uuid-...",
  "title": "新对话",
  "isNew": true,
  "messageCount": 0
}
```

### 发送消息 (非流式)
发送消息并等待完整回复，支持 RAG 检索和 Agent 工具调用。对于数据库未存储的会话，自动触发会话标题生成和数据库存储。

- **接口**: `POST /chatbox/message`
- **Body**:
```json
{
  "message": "这篇论文的主要贡献是什么？",
  "sessionId": "uuid-...",
  "pdfId": "a1b2c3...",      // 当前关联的 PDF ID
  "userId": "user_123"
}
```
- **响应**:
```json
{
  "response": "论文的主要贡献是...",
  "citations": [{"text": "...", "page": 1}], // 引用来源
  "sessionId": "uuid-..."
}
```

### 发送消息 (流式 SSE)
推荐使用。通过 Server-Sent Events 流式返回打字机效果。【未测试】

- **接口**: `POST /chatbox/stream`
- **Header**: `Accept: text/event-stream`
- **Body**: 同上 (`message`, `sessionId`, `pdfId`)
- **响应**: 流式数据，每行以 `data: ` 开头。
    - 中间状态: `{"content": "部分文本", "type": "chunk"}`
    - 结束状态: `{"response": "完整文本", "citations": [...], "type": "final"}`
    - 错误状态: `{"error": "...", "type": "error"}`

### 简单对话 (全文模式)
将 PDF 全文（或截断）作为上下文，作为简单对话回复。

- **接口**: `POST /chatbox/simple-chat`
- **Body**: 同上
- **响应**: 同非流式接口。

### 会话管理

#### 获取会话列表
获取用户的所有聊天会话，支持按 PDF 筛选。

- **接口**: `GET /chatbox/sessions`
- **Header**: `X-User-Id: user_123`
- **Query 参数**:
    - `pdfId`: (String, 可选) 筛选特定 PDF 的会话
    - `limit`: (Int, 可选, 默认 50) 返回数量限制
- **示例**: `GET /chatbox/sessions?pdfId=a1b2c3...&limit=20`
- **响应**:
```json
{
  "success": true,
  "sessions": [
    {
      "sessionId": "uuid-...",
      "title": "Transformer 架构详解",
      "pdfId": "a1b2c3...",
      "createdTime": "2026-01-22T10:30:00Z",
      "updatedTime": "2026-01-22T15:45:00Z",
      "messageCount": 8
    },
    {
      "sessionId": "uuid-...",
      "title": "注意力机制原理",
      "pdfId": "a1b2c3...",
      "createdTime": "2026-01-21T14:20:00Z",
      "updatedTime": "2026-01-21T16:30:00Z",
      "messageCount": 5
    }
  ],
  "total": 2
}
```

#### 获取会话历史消息
获取指定会话的所有对话消息。

- **接口**: `GET /chatbox/session/<session_id>/messages`
- **路径参数**:
    - `session_id`: (String) 会话 ID
- **示例**: `GET /chatbox/session/uuid-123/messages`
- **响应**:
```json
{
  "success": true,
  "sessionId": "uuid-123",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "这篇论文的主要贡献是什么？",
      "createdTime": "2026-01-22T10:30:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "这篇论文的主要贡献包括...",
      "citations": [
        {
          "source_type": "local",
          "page": 3,
          "section": "Introduction"
        }
      ],
      "createdTime": "2026-01-22T10:30:15Z"
    }
  ],
  "total": 2
}
```

#### 删除会话
删除指定会话及其所有消息。

- **接口**: `DELETE /chatbox/session/<session_id>`
- **路径参数**:
    - `session_id`: (String) 会话 ID
- **示例**: `DELETE /chatbox/session/uuid-123`
- **响应**:
```json
{
  "success": true,
  "sessionId": "uuid-123",
  "deletedMessages": 8,
  "message": "Session deleted with 8 messages"
}
```
- **错误响应** (404):
```json
{
  "error": "Session not found"
}
```

#### 更新会话标题
修改会话的显示标题。

- **接口**: `PUT /chatbox/session/<session_id>/title`
- **路径参数**:
    - `session_id`: (String) 会话 ID
---

## 5. 高亮标注 (`/api/highlight`)

### 创建高亮
保存前端 PDF.js 选中的区域。后端会自动将像素坐标转换为相对坐标（0.0-1.0）。

- **接口**: `POST /highlight/`
- **Body**:
```json
{
  "pdfId": "a1b2c3...",
  "page": 1,
  "rects": [{"x": 100, "y": 100, "width": 50, "height": 20}], // 前端原始坐标
  "pageWidth": 800,   // 当前 Canvas 宽度
  "pageHeight": 1200, // 当前 Canvas 高度
  "text": "选中的文本内容",
  "color": "#FFFF00",
  "comment": "这是一个重点"
}
```
- **响应**:
```json
{
  "success": true,
  "id": 1,
  "rects": [{"x0": 0.125, "y0": 0.083, ...}] // 归一化后的相对坐标
}
```

### 获取高亮列表
- **接口**: `GET /highlight/<pdf_id>`
- **Query 参数**: `page` (Int, 可选)
- **响应**: 返回该 PDF 的所有高亮数据（含相对坐标、颜色、笔记）。

### 管理高亮
*   **删除高亮**: `DELETE /highlight/<highlight_id>`
*   **更新高亮**: `PUT /highlight/<highlight_id>`
    *   Body: `{"color": "#...", "comment": "..."}`

---

## 6. 翻译服务 (`/api/translate`)

### 翻译指定段落
翻译 PDF 解析后的特定段落，支持缓存。

- **接口**: `POST /translate/paragraph`
- **Body**:
```json
{
  "pdfId": "a1b2c3...",
  "paragraphId": "pdf_chk_a1b2c3_1_5", // 格式: pdf_chk_{hash前8位}_{页码}_{索引}
  "force": false // 是否强制重新翻译（忽略缓存）
}
```
- **响应**:
```json
{
  "success": true,
  "translation": "翻译后的中文文本...",
  "cached": true // 是否命中了数据库缓存
}
```

### 获取整页翻译缓存
用于页面加载时批量获取已存在的翻译。

- **接口**: `GET /translate/page/<pdf_id>/<page_number>`
- **响应**:
```json
{
  "translations": {
    "pdf_chk_..._1_5": "翻译文本A",
    "pdf_chk_..._1_6": "翻译文本B"
  }
}
```

### 划词翻译 (带上下文)
翻译任意选中的文本，后端会自动获取 PDF 前几段作为上下文以提高准确度。

- **接口**: `POST /translate/text`
- **Body**:
```json
{
  "text": "selected text to translate",
  "pdfId": "a1b2c3...", // 可选，提供则自动获取上下文
  "contextParagraphs": 5 // 可选，上下文段落数
}
```
- **响应**:
```json
{
  "originalText": "...",
  "translatedText": "...",
  "hasContext": true
}
```