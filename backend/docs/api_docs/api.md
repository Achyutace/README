# 后端 API 接口文档

## 1. 基础说明

- **Base URL**: `http://localhost:5000/api`
- **鉴权与用户隔离**: 后端采用 **JWT (JSON Web Token)** 进行认证。
    - 用户通过 `/api/auth/login` 或 `/api/auth/register` 获取 `accessToken`。同时，`refreshToken` 将通过后端生成的 `HttpOnly` Cookie 注入浏览器中防范窃取。
    - 受保护接口需在请求头中携带 `Authorization: Bearer <accessToken>`。
    - Access Token 过期后，前端可通过 `/api/auth/refresh` 接口使用 Refresh Token 换取新的 Access Token。
- **公开接口**: `/api/auth/register`、`/api/auth/login`、`/api/auth/refresh`、`/api/health` 不需要认证。
- **跨域**: 已通过 Flask-CORS 开启，允许所有来源访问 `/api/*`。
- **文件大小限制**: 上传文件最大 100MB。
- **需鉴权接口**: 除特别说明外，所有接口均需在请求头携带 `Authorization: Bearer <accessToken>`，由 `@require_auth` 装饰器校验 JWT 有效性，否则返回 `401 Unauthorized`。

---

## 2. 系统检测

### 2.1 健康检查

检测后端服务及各组件（数据库、RAG、Agent等）的初始化状态。

- **接口**: `GET /health`
- **请求参数**: 无
- **成功响应** (`200`):

```json
{
  "status": "ok",
  "user_id": "default_user",
  "services": {
    "storage": true,
    "rag": true,
    "translate": true,
    "agent": true,
    "chat": true,
    "celery": true
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | String | 固定值 `"ok"` |
| `user_id` | String | 当前请求解析到的用户 UUID |
| `services` | Object | 各服务初始化状态 |
| `services.celery` | Boolean | Celery 是否可用 |
| `services.rag` | Boolean | RAG 服务是否已初始化 |
| `services.translate` | Boolean | 翻译服务是否已初始化 |
| `services.agent` | Boolean | Agent 服务是否已初始化 |
| `services.chat` | Boolean | 聊天服务是否已初始化 |

---

## 3. PDF 文件管理 (`/api/pdf`)

### 3.1 上传 PDF

上传文件，计算 Hash，解析段落，响应给前端，并触发后台数据库存储和 RAG 索引构建。

- **接口**: `POST /pdf/upload`
- **Content-Type**: `multipart/form-data`
- **说明**: 上传 PDF 文件。后端执行：计算文件 Hash 查重 → 本地存盘 → COS 上传（如启用） → 写入 GlobalFile 数据库记录 → 触发 Celery 异步解析任务 → 绑定到用户书架。
- **请求参数**:

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `file` | FormData | File | 是 | PDF 文件，仅接受 `.pdf` 后缀 |

- **成功响应** (`200`):

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `pdfId` | String | 文件 Hash，作为 PDF 的全局唯一标识 |
| `taskId` | String | Celery 异步任务 ID，用于轮询处理进度 |
| `status` | String | 处理状态：`"pending"` / `"processing"` / `"completed"` / `"failed"` |
| `pageCount` | Integer | PDF 总页数 |
| `filename` | String | 上传时的原始文件名 |
| `userId` | String (UUID) | 当前用户 UUID |
| `isNewUpload` | Boolean | `true` 表示新上传；`false` 表示文件已存在（秒传） |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 未提供 file 字段 | `{ "error": "No file provided" }` |
| `400` | 文件名为空 | `{ "error": "No file selected" }` |
| `400` | 非 PDF 文件 | `{ "error": "Only PDF files are allowed" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

### 3.2 获取 PDF 处理进度

轮询 PDF 的异步解析进度，支持增量拉取已解析段落。

- **接口**: `GET /pdf/<pdf_id>/status`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **Query 参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `from_page` | Integer | 否 | `1` | 从第几页开始返回段落（1-based），用于增量拉取 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | String | `"pending"` / `"processing"` / `"completed"` / `"failed"` / `"not_found"` / `"error"` |
| `currentPage` | Integer | 当前已处理到的页码 |
| `totalPages` | Integer | PDF 总页数 |
| `error` | String \| null | 错误信息（仅 `failed` / `error` 状态下有值） |
| `paragraphs` | Array | 从 `from_page` 到 `currentPage` 的段落数组 |

- **`paragraphs` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String | 段落 ID，格式 `pdf_chk_{hash前缀}_{页码}_{索引}` |
| `page` | Integer | 所在页码 |
| `bbox` | Array | 段落边界框坐标 |
| `content` | String | 段落原文文本 |
| `wordCount` | Integer | 英文单词数 |
| `translation` | String \| null | 已有的翻译文本（如尚未翻译则为 null） |

### 3.3 获取 PDF 元数据

获取 PDF 的基本信息（文件名、页数、上传时间等）。

- **接口**: `GET /pdf/<pdf_id>/info`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String | 文件 Hash |
| `pageCount` | Integer | 总页数 |
| `metadata` | Object | PDF 元数据信息（标题、作者等，内容视文件而定） |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `404` | PDF 不存在 | `{ "error": "PDF not found" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

### 3.4 获取 PDF 段落数据

从数据库读取已解析的段落。

- **接口**: `GET /pdf/<pdf_id>/paragraphs`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | Integer | 否 | 指定页码，不传则返回全部页 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `paragraphs` | Array | 段落数据块数组 |

- **`paragraphs` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | String | 段落文本内容 |
| `pageNumber` | Integer | 所在页码 |
| `bbox` | Array | 边界框坐标 `[x0, y0, x1, y1]` |

### 3.5 获取 PDF 源文件

获取 PDF 原始文件流，可用于浏览器直接预览渲染。

- **接口**: `GET /pdf/<pdf_id>/source`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **成功响应** (`200`):
    - **Content-Type**: `application/pdf`
    - **Body**: PDF 文件二进制流

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `404` | 文件不存在 | `{ "error": "PDF file not found" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

### 3.6 获取 PDF 纯文本

- **接口**: `GET /pdf/<pdf_id>/text`
- **Query 参数**:
    - `page`: (Int, 可选) 指定页码
- **响应**: 返回指定页或全文的文本内容。

---

## 4. 聊天对话 (`/api/chatbox`)

### 4.1 创建新会话

仅生成一个前端使用的会话 UUID，不写入数据库（懒创建策略：直到第一条消息发送时才创建数据库记录）。

- **接口**: `POST /chatbox/new`
- **请求参数**: 无（Body 可为空）
- **成功响应** (`200`):

```json
{
  "sessionId": "uuid-...",
  "title": "新对话",
  "isNew": true,
  "messageCount": 0
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `sessionId` | String | 新生成的 UUID 会话 ID |
| `title` | String | 默认标题 `"新对话"` |
| `isNew` | Boolean | 固定 `true` |
| `messageCount` | Integer | 固定 `0` |

### 4.2 发送消息（非流式）

发送消息并等待完整回复。后端依次执行：懒创建会话（首次消息时写库并异步生成标题） → 存储用户消息 → 获取历史记录 → 调用 Agent（含 RAG 检索 + 工具调用） → 存储 AI 回复 → 返回。

- **接口**: `POST /chatbox/message`
- **Content-Type**: `application/json`
- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | String | 是 | 用户发送的消息内容 |
| `sessionId` | String | 是 | 会话 ID |
| `pdfId` | String | 否 | 当前关联的 PDF 文件 Hash |

- **示例请求**:

```json
{
  "message": "这篇论文的主要贡献是什么？",
  "sessionId": "uuid-...",
  "pdfId": "a1b2c3...",
  "userId": "123e4567-e89b-12d3-a456-426614174000"
}
```

- **成功响应** (`200`):

```json
{
  "response": "论文的主要贡献是...",
  "citations": [{"text": "...", "page": 1}],
  "sessionId": "uuid-..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `response` | String | AI 的完整回复文本 |
| `citations` | Array | 引用来源列表 |
| `steps` | Array | Agent 执行步骤记录 |
| `sessionId` | String | 当前会话 ID |

- **`citations` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_type` | String | 来源类型（`"local"` / `"web"` 等） |
| `page` | Integer | 引用的 PDF 页码（本地来源时） |
| `section` | String | 引用的章节信息 |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 缺少 `message` 或 `sessionId` | `{ "error": "Message and sessionId are required" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

### 4.3 简单对话（全文模式）

将 PDF 全文作为上下文进行简单对话，不使用 RAG 检索，适用于轻量场景。

- **接口**: `POST /chatbox/simple-chat`
- **Content-Type**: `application/json`
- **请求参数** (Body): 同 4.2
- **成功响应** (`200`): 同 4.2 非流式接口

### 4.4 发送消息（流式 SSE）

通过 Server-Sent Events 流式返回，实现打字机效果。

- **接口**: `POST /chatbox/stream`
- **Header**: `Accept: text/event-stream`
- **Content-Type**: `application/json`
- **请求参数** (Body): 同 4.2
- **成功响应** (`200`):
    - **Content-Type**: `text/event-stream`
    - **响应头**: `Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Connection: keep-alive`
    - **流式数据格式**: 每行以 `data: ` 开头，后跟 JSON

- **流式事件类型**:

| type 值 | 说明 | 包含字段 |
|---------|------|----------|
| `"chunk"` | 中间文本片段 | `content` (String): 部分文本 |
| `"step"` | Agent 执行步骤 | `step` (String): 当前步骤描述 |
| `"final"` | 最终完整结果 | `response` (String): 完整回复文本；`citations` (Array): 引用列表 |
| `"error"` | 错误 | `error` (String): 错误信息 |

### 4.5 获取会话列表

获取当前用户的所有聊天会话，支持按 PDF 筛选。

- **接口**: `GET /chatbox/sessions`
- **Query 参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pdfId` | String | 否 | 无 | 按指定 PDF 文件 Hash 筛选 |
| `limit` | Integer | 否 | `50` | 返回数量限制 |

- **成功响应** (`200`):

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
    }
  ],
  "total": 1
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `sessions` | Array | 会话列表 |
| `total` | Integer | 返回的会话数量 |

### 4.6 获取会话历史消息

获取指定会话的所有对话消息。

- **接口**: `GET /chatbox/session/<session_id>/messages`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | String | 会话 UUID |

- **成功响应** (`200`):

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
      "citations": [],
      "createdTime": "2026-01-22T10:30:15Z"
    }
  ],
  "total": 2
}
```

### 4.7 更新会话标题

修改会话的显示标题。

- **接口**: `PUT /chatbox/session/<session_id>/title`
- **路径参数**:
    - `session_id`: (String) 会话 ID

### 4.8 删除会话

删除指定会话及其所有消息。

- **接口**: `DELETE /chatbox/session/<session_id>`
- **路径参数**:
    - `session_id`: (String) 会话 ID
- **成功响应** (`200`):

```json
{
  "success": true,
  "sessionId": "uuid-123",
  "deletedMessages": 8,
  "message": "Session deleted with 8 messages"
}
```

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `404` | 会话不存在 | `{ "error": "Session not found" }` |
| `500` | 删除失败 | `{ "error": "<错误信息>" }` |

---

### 4.8 更新会话标题

修改会话的显示标题。

- **请求方式**: `PUT`
- **请求地址**: `/api/chatbox/session/<session_id>/title`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | String | 会话 UUID |

- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | String | 是 | 新的会话标题 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `sessionId` | String | 会话 ID |
| `title` | String | 更新后的标题 |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 标题为空 | `{ "error": "Title is required" }` |
| `404` | 会话不存在或更新失败 | `{ "error": "Session not found or update failed" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

---

## 5. 高亮标注 (`/api/highlight`)

### 5.1 创建高亮

保存 PDF 上的高亮区域。前端传入像素坐标，后端自动转换为归一化相对坐标（0.0 - 1.0）。

- **接口**: `POST /highlight/`
- **Content-Type**: `application/json`
- **请求参数** (Body):

```json
{
  "pdfId": "a1b2c3...",
  "page": 1,
  "rects": [{"x": 100, "y": 100, "width": 50, "height": 20}],
  "pageWidth": 800,
  "pageHeight": 1200,
  "text": "选中的文本内容",
  "color": "#FFFF00",
  "comment": "这是一个重点"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pdfId` | String | 是 | PDF 文件 Hash |
| `page` | Integer | 是 | 高亮所在页码 |
| `rects` | Array | 是 | 选区矩形数组，每项含 `x`, `y`, `width`, `height`（像素坐标） |
| `pageWidth` | Float | 是 | 当前 Canvas 渲染宽度（像素） |
| `pageHeight` | Float | 是 | 当前 Canvas 渲染高度（像素） |
| `text` | String | 否 | 选中的文本内容 |
| `color` | String | 否 | 高亮颜色（默认 `"#FFFF00"`） |

- **成功响应** (`200`):

```json
{
  "success": true,
  "id": 1,
  "rects": [{"x0": 0.125, "y0": 0.083, "x1": 0.1875, "y1": 0.1}], // 归一化后的相对坐标
  "message": "Highlight created"
}
```

### 5.2 获取高亮列表

获取某 PDF 的所有高亮，返回归一化坐标，前端需乘以当前 Canvas 尺寸进行渲染。

- **接口**: `GET /highlight/<pdf_id>`
- **Query 参数**:
    - `page`: (Int, 可选) 按页码筛选

- **成功响应** (`200`):

```json
{
  "success": true,
  "highlights": [
    {
      "id": 1,
      "page": 1,
      "rects": [{"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2}],
      "text": "重点内容",
      "color": "#FFFF00",
      "created_at": "2026-01-22T10:00:00Z"
    }
  ],
  "total": 1
}
```

### 5.3 删除高亮

- **接口**: `DELETE /highlight/<highlight_id>`

### 5.4 更新高亮

- **接口**: `PUT /highlight/<highlight_id>`
- **请求参数** (Body): `{"color": "#...", "comment": "..."}`

---

## 6. 翻译服务 (`/api/translate`)

### 6.1 翻译指定段落

按需翻译 PDF 中的特定段落，支持数据库缓存。后端流程：解析段落 ID → 从 DB 查原文 → 检查缓存 → 调用 LLM 翻译 → 写入 DB。

- **接口**: `POST /translate/paragraph`
- **Content-Type**: `application/json`
- **请求参数** (Body):

```json
{
  "pdfId": "a1b2c3...",
  "paragraphId": "pdf_chk_a1b2c3_1_5",
  "force": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pdfId` | String | 是 | PDF 文件 Hash |
| `paragraphId` | String | 是 | 段落 ID，格式 `pdf_chk_{hash前缀}_{页码}_{索引}` |
| `force` | Boolean | 否 | 是否强制重新翻译（忽略缓存），默认 `false` |

- **成功响应** (`200`):

```json
{
  "success": true,
  "translation": "翻译后的中文文本...",
  "cached": true,
  "paragraphId": "pdf_chk_a1b2c3_1_5"
}
```

### 6.2 获取整页翻译缓存

批量获取某一页中所有已翻译段落的缓存，适用于页面加载时一次性获取。

- **接口**: `GET /translate/page/<pdf_id>/<page_number>`
- **成功响应** (`200`):

```json
{
  "translations": {
    "pdf_chk_..._1_5": "翻译文本A",
    "pdf_chk_..._1_6": "翻译文本B"
  }
}
```

### 6.3 划词翻译（带上下文）

翻译任意选中的文本。如提供了 `pdfId`，后端会自动从数据库获取 PDF 前几段文本作为上下文以提高翻译准确度。

- **接口**: `POST /translate/text`
- **Content-Type**: `application/json`
- **请求参数** (Body):

```json
{
  "text": "selected text to translate",
  "pdfId": "a1b2c3...",
  "contextParagraphs": 3
}
```

- **成功响应** (`200`):

```json
{
  "success": true,
  "originalText": "...",
  "translatedText": "...",
  "hasContext": true
}
```

---

## 7. 笔记管理 (`/api/notes`)

### 7.1 创建笔记

为指定 PDF 创建一条笔记。

- **接口**: `POST /api/notes`
- **Content-Type**: `application/json`
- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pdfId` | String | 是 | PDF 文件 Hash |
| `content` | String | 否 | 笔记内容（Markdown） |
| `title` | String | 否 | 笔记标题 |
| `keywords` | Array\<String\> | 否 | 关键词列表 |

- **成功响应** (`200`):

```json
{
  "success": true,
  "id": 1,
  "message": "Note created"
}
```

### 7.2 获取笔记列表

获取用户针对某 PDF 的所有笔记。

- **接口**: `GET /api/notes/<pdf_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **成功响应** (`200`):

```json
{
  "success": true,
  "notes": [
    {
      "id": 1,
      "title": "笔记标题",
      "content": "笔记内容",
      "keywords": ["关键词1", "关键词2"],
      "createdAt": "2026-02-15T10:00:00Z",
      "updatedAt": "2026-02-15T10:00:00Z"
    }
  ],
  "total": 1
}
```

### 7.3 更新笔记

支持部分更新，即仅更新提供的字段。

- **接口**: `PUT /api/notes/<note_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `note_id` | Integer | 笔记 ID |

- **请求参数** (Body): 至少提供其中一个字段

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | String | 否 | 新笔记内容 |
| `title` | String | 否 | 新标题 |
| `keywords` | Array\<String\> | 否 | 新关键词列表 |

- **成功响应** (`200`):

```json
{
  "success": true,
  "message": "Note updated"
}
```

- **错误响应**:

| 状态码 | 条件 | 说明 |
|--------|------|------|
| `400` | 所有字段均为空 | `{ "error": "At least one field (title, content, keywords) must be provided" }` |
| `404` | 笔记不存在 | `{ "error": "Note not found" }` |

### 7.4 删除笔记

- **接口**: `DELETE /api/notes/<note_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `note_id` | Integer | 笔记 ID |

- **成功响应** (`200`):

```json
{
  "success": true,
  "message": "Note deleted"
}
```

---

## 8. 通用错误响应格式

所有接口在发生异常时，统一返回以下格式：

```json
{
  "error": "错误描述信息"
}
```

鉴权失败时返回 `401`：

```json
{
  "error": "Unauthorized: user identity not resolved"
}
```
