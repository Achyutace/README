# 后端 API 接口文档



## 1. 基础说明



- **Base URL**: `http://localhost:5000/api`* 

- **鉴权与用户隔离**: 后端通过 `before_request` 钩子统一解析用户身份。
  优先级为：请求头 `X-User-Id` > 表单字段 `userId` > URL 参数 `userId` > 
  默认值 `default_user`。传入值可以是 UUID 字符串或普通用户名，后端自动在数据库中 `get_or_create` 对应用户记录，并将 `user_id` (UUID) 挂载到请求上下文 `g` 中。

- **跨域**: 已通过 Flask-CORS 开启，允许所有来源访问 `/api/*`。   

- **文件大小限制**: 上传文件最大 100MB。   
- **需鉴权接口**: 除特别说明外，所有接口均需通过 `@require_auth` 装饰器校验 `g.user_id` 存在，否则返回 `401 Unauthorized`。


------



## 2. 系统检测## 2. 系统检测



### 2.1 健康检查### 健康检查

检测后端服务及各组件（数据库、RAG、Agent等）的初始化状态。

检测后端服务及各组件的初始化状态。

- **接口**: `GET /health`

- **请求方式**: `GET`- **响应示例**:

- **请求地址**: `/api/health````json

- **请求参数**: 无{

- **成功响应** (`200`):  "status": "ok",

  "user_id": "default_user",

| 字段 | 类型 | 说明 |  "services": {

|------|------|------|    "storage": true,

| `status` | String | 固定值 `"ok"` |    "rag": true,

| `user_id` | String | 当前请求解析到的用户 UUID |    "translate": true,

| `services` | Object | 各服务初始化状态 |    "agent": true,

| `services.celery` | Boolean | Celery 是否可用（固定 `true`） |    "chat": true

| `services.rag` | Boolean | RAG 服务是否已初始化 |  }

| `services.translate` | Boolean | 翻译服务是否已初始化 |}

| `services.agent` | Boolean | Agent 服务是否已初始化 |```

| `services.chat` | Boolean | 聊天服务是否已初始化 |

## 3. PDF 文件管理 (`/api/pdf`)

---

### 上传 PDF

## 3. PDF 文件管理 (`/api/pdf`)上传文件，计算 Hash，解析段落，响应给前端，并触发后台数据库存储和RAG索引构建。



### 3.1 上传 PDF- **接口**: `POST /pdf/upload`

- **Content-Type**: `multipart/form-data`

上传 PDF 文件。后端执行：计算文件 Hash 查重 → 本地存盘 → COS 上传（如启用） → 写入 GlobalFile 数据库记录 → 触发 Celery 异步解析任务 → 绑定到用户书架。- **参数**:

    - `file`: (File) PDF 文件对象

- **请求方式**: `POST`- **响应**:

- **请求地址**: `/api/pdf/upload````json

- **Content-Type**: `multipart/form-data`{

- **请求参数**:  "id": "a1b2c3...",          // 文件 Hash，作为 pdfId

  "filename": "paper.pdf",

| 参数 | 位置 | 类型 | 必填 | 说明 |  "pageCount": 10,

|------|------|------|------|------|  "fileHash": "a1b2c3...",

| `file` | FormData | File | 是 | PDF 文件，仅接受 `.pdf` 后缀 |  "paragraphs": [...],        // 解析出的段落数据

  "status": "processing",     // 标识后台正在进行 RAG 索引

- **成功响应** (`200`):  "isNewUpload": true         // false 表示秒传（文件已存在）

}

| 字段 | 类型 | 说明 |```

|------|------|------|

| `pdfId` | String | 文件 Hash，作为 PDF 的全局唯一标识 |### 获取 PDF 元数据

| `taskId` | String | Celery 异步任务 ID，用于轮询处理进度 |- **接口**: `GET /pdf/<pdf_id>/info`

| `status` | String | 处理状态：`"pending"` / `"processing"` / `"completed"` / `"failed"` |- **响应**: PDF 的基本信息（文件名、页数、上传时间等）。

| `pageCount` | Integer | PDF 总页数 |

| `filename` | String | 上传时的原始文件名 |### 获取 PDF 纯文本

| `userId` | String | 当前用户 UUID |- **接口**: `GET /pdf/<pdf_id>/text`

| `isNewUpload` | Boolean | `true` 表示新上传；`false` 表示文件已存在（秒传） |- **Query 参数**:

    - `page`: (Int, 可选) 指定页码

- **错误响应**:- **响应**: 返回指定页或全文的文本内容。



| 状态码 | 条件 | 错误字段 |---

|--------|------|----------|

| `400` | 未提供 file 字段 | `{ "error": "No file provided" }` |## 4. 聊天对话 (`/api/chatbox`)

| `400` | 文件名为空 | `{ "error": "No file selected" }` |

| `400` | 非 PDF 文件 | `{ "error": "Only PDF files are allowed" }` |### 创建新会话

| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |生成一个新的会话 ID，返回给前端。



---- **接口**: `POST /chatbox/new`

- **响应**:

### 3.2 获取 PDF 处理进度```json

{

轮询 PDF 的异步解析进度，支持增量拉取已解析段落。  "sessionId": "uuid-...",

  "title": "新对话",

- **请求方式**: `GET`  "isNew": true,

- **请求地址**: `/api/pdf/<pdf_id>/status`  "messageCount": 0

- **路径参数**:}

```

| 参数 | 类型 | 说明 |

|------|------|------|### 发送消息 (非流式)

| `pdf_id` | String | PDF 文件 Hash |发送消息并等待完整回复，支持 RAG 检索和 Agent 工具调用。对于数据库未存储的会话，自动触发会话标题生成和数据库存储。



- **Query 参数**:- **接口**: `POST /chatbox/message`

- **Body**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |```json

|------|------|------|--------|------|{

| `from_page` | Integer | 否 | `1` | 从第几页开始返回段落（1-based），用于增量拉取 |  "message": "这篇论文的主要贡献是什么？",

  "sessionId": "uuid-...",

- **成功响应** (`200`):  "pdfId": "a1b2c3...",      // 当前关联的 PDF ID

  "userId": "user_123"

| 字段 | 类型 | 说明 |}

|------|------|------|```

| `status` | String | `"pending"` / `"processing"` / `"completed"` / `"failed"` / `"not_found"` / `"error"` |- **响应**:

| `currentPage` | Integer | 当前已处理到的页码 |```json

| `totalPages` | Integer | PDF 总页数 |{

| `error` | String \| null | 错误信息（仅 `failed` / `error` 状态下有值） |  "response": "论文的主要贡献是...",

| `paragraphs` | Array | 从 `from_page` 到 `currentPage` 的段落数组 |  "citations": [{"text": "...", "page": 1}], // 引用来源

  "sessionId": "uuid-..."

- **`paragraphs` 数组中每个元素**:}

```

| 字段 | 类型 | 说明 |

|------|------|------|### 发送消息 (流式 SSE)

| `id` | String | 段落 ID，格式 `pdf_chk_{hash前缀}_{页码}_{索引}` |推荐使用。通过 Server-Sent Events 流式返回打字机效果。【未测试】

| `page` | Integer | 所在页码 |

| `bbox` | Array | 段落边界框坐标 |- **接口**: `POST /chatbox/stream`

| `content` | String | 段落原文文本 |- **Header**: `Accept: text/event-stream`

| `wordCount` | Integer | 英文单词数 |- **Body**: 同上 (`message`, `sessionId`, `pdfId`)

| `translation` | String \| null | 已有的翻译文本（如尚未翻译则为 null） |- **响应**: 流式数据，每行以 `data: ` 开头。

    - 中间状态: `{"content": "部分文本", "type": "chunk"}`

---    - 结束状态: `{"response": "完整文本", "citations": [...], "type": "final"}`

    - 错误状态: `{"error": "...", "type": "error"}`

### 3.3 获取 PDF 元数据

### 简单对话 (全文模式)

- **请求方式**: `GET`将 PDF 全文（或截断）作为上下文，作为简单对话回复。

- **请求地址**: `/api/pdf/<pdf_id>/info`

- **路径参数**:- **接口**: `POST /chatbox/simple-chat`

- **Body**: 同上

| 参数 | 类型 | 说明 |- **响应**: 同非流式接口。

|------|------|------|

| `pdf_id` | String | PDF 文件 Hash |### 会话管理



- **成功响应** (`200`):#### 获取会话列表

获取用户的所有聊天会话，按 PDF 筛选。

| 字段 | 类型 | 说明 |

|------|------|------|- **接口**: `GET /chatbox/sessions`

| `id` | String | 文件 Hash |- **Header**: `X-User-Id: user_123`

| `pageCount` | Integer | 总页数 |- **Query 参数**:

| `metadata` | Object | PDF 元数据信息（标题、作者等，内容视文件而定） |    - `pdfId`: (String) 筛选特定 PDF 的会话

    - `limit`: (Int, 可选, 默认 50) 返回数量限制

- **错误响应**:- **示例**: `GET /chatbox/sessions?pdfId=a1b2c3...&limit=20`

- **响应**:

| 状态码 | 条件 | 错误字段 |```json

|--------|------|----------|{

| `404` | PDF 不存在 | `{ "error": "PDF not found" }` |  "success": true,

| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |  "sessions": [

    {

---      "sessionId": "uuid-...",

      "title": "Transformer 架构详解",

### 3.4 获取 PDF 段落数据      "pdfId": "a1b2c3...",

      "createdTime": "2026-01-22T10:30:00Z",

从数据库读取已解析的段落。      "updatedTime": "2026-01-22T15:45:00Z",

      "messageCount": 8

- **请求方式**: `GET`    },

- **请求地址**: `/api/pdf/<pdf_id>/paragraphs`    {

- **路径参数**:      "sessionId": "uuid-...",

      "title": "注意力机制原理",

| 参数 | 类型 | 说明 |      "pdfId": "a1b2c3...",

|------|------|------|      "createdTime": "2026-01-21T14:20:00Z",

| `pdf_id` | String | PDF 文件 Hash |      "updatedTime": "2026-01-21T16:30:00Z",

      "messageCount": 5

- **Query 参数**:    }

  ],

| 参数 | 类型 | 必填 | 说明 |  "total": 2

|------|------|------|------|}

| `page` | Integer | 否 | 指定页码，不传则返回全部页 |```



- **成功响应** (`200`):#### 获取会话历史消息

获取指定会话的所有对话消息。

| 字段 | 类型 | 说明 |

|------|------|------|- **接口**: `GET /chatbox/session/<session_id>/messages`

| `paragraphs` | Array | 段落数据块数组 |- **路径参数**:

    - `session_id`: (String) 会话 ID

- **`paragraphs` 数组中每个元素**:- **示例**: `GET /chatbox/session/uuid-123/messages`

- **响应**:

| 字段 | 类型 | 说明 |```json

|------|------|------|{

| `text` | String | 段落文本内容 |  "success": true,

| `pageNumber` | Integer | 所在页码 |  "sessionId": "uuid-123",

| `bbox` | Array | 边界框坐标 `[x0, y0, x1, y1]` |  "messages": [

    {

---      "id": 1,

      "role": "user",

### 3.5 获取 PDF 源文件      "content": "这篇论文的主要贡献是什么？",

      "createdTime": "2026-01-22T10:30:00Z"

获取 PDF 原始文件流，可用于浏览器直接预览渲染。    },

    {

- **请求方式**: `GET`      "id": 2,

- **请求地址**: `/api/pdf/<pdf_id>/source`      "role": "assistant",

- **路径参数**:      "content": "这篇论文的主要贡献包括...",

      "citations": [

| 参数 | 类型 | 说明 |        {

|------|------|------|          "source_type": "local",

| `pdf_id` | String | PDF 文件 Hash |          "page": 3,

          "section": "Introduction"

- **成功响应** (`200`):        }

  - **Content-Type**: `application/pdf`      ],

  - **Body**: PDF 文件二进制流      "createdTime": "2026-01-22T10:30:15Z"

    }

- **错误响应**:  ],

  "total": 2

| 状态码 | 条件 | 错误字段 |}

|--------|------|----------|```

| `404` | 文件不存在 | `{ "error": "PDF file not found" }` |

| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |#### 删除会话

删除指定会话及其所有消息。

---

- **接口**: `DELETE /chatbox/session/<session_id>`

## 4. 聊天对话 (`/api/chatbox`)- **路径参数**:

    - `session_id`: (String) 会话 ID

### 4.1 创建新会话- **示例**: `DELETE /chatbox/session/uuid-123`

- **响应**:

仅生成一个前端使用的会话 UUID，不写入数据库（懒创建策略：直到第一条消息发送时才创建数据库记录）。```json

{

- **请求方式**: `POST`  "success": true,

- **请求地址**: `/api/chatbox/new`  "sessionId": "uuid-123",

- **请求参数**: 无（Body 可为空）  "deletedMessages": 8,

- **成功响应** (`200`):  "message": "Session deleted with 8 messages"

}

| 字段 | 类型 | 说明 |```

|------|------|------|- **错误响应** (404):

| `sessionId` | String | 新生成的 UUID 会话 ID |```json

| `title` | String | 默认标题 `"新对话"` |{

| `isNew` | Boolean | 固定 `true` |  "error": "Session not found"

| `messageCount` | Integer | 固定 `0` |}

```

---

#### 更新会话标题

### 4.2 发送消息（非流式）修改会话的显示标题。



发送消息并等待完整回复。后端依次执行：懒创建会话（首次消息时写库并异步生成标题） → 存储用户消息 → 获取历史记录 → 调用 Agent（含 RAG 检索 + 工具调用） → 存储 AI 回复 → 返回。- **接口**: `PUT /chatbox/session/<session_id>/title`

- **路径参数**:

- **请求方式**: `POST`    - `session_id`: (String) 会话 ID

- **请求地址**: `/api/chatbox/message`---

- **Content-Type**: `application/json`

- **请求参数** (Body):## 5. 高亮标注 (`/api/highlight`)



| 参数 | 类型 | 必填 | 说明 |### 创建高亮

|------|------|------|------|保存前端 PDF.js 选中的区域。后端会自动将像素坐标转换为相对坐标（0.0-1.0）。

| `message` | String | 是 | 用户发送的消息内容 |

| `sessionId` | String | 是 | 会话 ID |- **接口**: `POST /highlight/`

| `pdfId` | String | 否 | 当前关联的 PDF 文件 Hash |- **Body**:

```json

- **成功响应** (`200`):{

  "pdfId": "a1b2c3...",

| 字段 | 类型 | 说明 |  "page": 1,

|------|------|------|  "rects": [{"x": 100, "y": 100, "width": 50, "height": 20}], // 前端原始坐标

| `response` | String | AI 的完整回复文本 |  "pageWidth": 800,   // 当前 Canvas 宽度

| `citations` | Array | 引用来源列表 |  "pageHeight": 1200, // 当前 Canvas 高度

| `steps` | Array | Agent 执行步骤记录 |  "text": "选中的文本内容",

| `sessionId` | String | 当前会话 ID |  "color": "#FFFF00",

  "comment": "这是一个重点"

- **`citations` 数组中每个元素**:}

```

| 字段 | 类型 | 说明 |- **响应**:

|------|------|------|```json

| `source_type` | String | 来源类型（`"local"` / `"web"` 等） |{

| `page` | Integer | 引用的 PDF 页码（本地来源时） |  "success": true,

| `section` | String | 引用的章节信息 |  "id": 1,

  "rects": [{"x0": 0.125, "y0": 0.083, ...}] // 归一化后的相对坐标

- **错误响应**:}

```

| 状态码 | 条件 | 错误字段 |

|--------|------|----------|### 获取高亮列表

| `400` | 缺少 `message` 或 `sessionId` | `{ "error": "Message and sessionId are required" }` |- **接口**: `GET /highlight/<pdf_id>`

| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |- **Query 参数**: `page` (Int, 可选)

- **响应**: 返回该 PDF 的所有高亮数据（含相对坐标、颜色、笔记）。

---

### 管理高亮

### 4.3 简单对话（全文模式）*   **删除高亮**: `DELETE /highlight/<highlight_id>`

*   **更新高亮**: `PUT /highlight/<highlight_id>`

将 PDF 全文作为上下文进行简单对话，不使用 RAG 检索，适用于轻量场景。    *   Body: `{"color": "#...", "comment": "..."}`



- **请求方式**: `POST`---

- **请求地址**: `/api/chatbox/simple-chat`

- **Content-Type**: `application/json`## 6. 翻译服务 (`/api/translate`)

- **请求参数** (Body):

### 翻译指定段落

| 参数 | 类型 | 必填 | 说明 |翻译 PDF 解析后的特定段落，支持缓存。

|------|------|------|------|

| `message` | String | 是 | 用户发送的消息内容 |- **接口**: `POST /translate/paragraph`

| `sessionId` | String | 是 | 会话 ID |- **Body**:

| `pdfId` | String | 否 | 当前关联的 PDF 文件 Hash |```json

{

- **成功响应** (`200`): 同 4.2 非流式接口  "pdfId": "a1b2c3...",

  "paragraphId": "pdf_chk_a1b2c3_1_5", // 格式: pdf_chk_{hash前8位}_{页码}_{索引}

- **错误响应**: 同 4.2  "force": false // 是否强制重新翻译（忽略缓存）

}

---```

- **响应**:

### 4.4 发送消息（流式 SSE）```json

{

通过 Server-Sent Events 流式返回，实现打字机效果。  "success": true,

  "translation": "翻译后的中文文本...",

- **请求方式**: `POST`  "cached": true // 是否命中了数据库缓存

- **请求地址**: `/api/chatbox/stream`}

- **Content-Type**: `application/json````

- **请求参数** (Body): 同 4.2

### 获取整页翻译缓存

- **成功响应** (`200`):用于页面加载时批量获取已存在的翻译。

  - **Content-Type**: `text/event-stream`

  - **响应头**: `Cache-Control: no-cache`、`X-Accel-Buffering: no`、`Connection: keep-alive`- **接口**: `GET /translate/page/<pdf_id>/<page_number>`

  - **流式数据格式**: 每行以 `data: ` 开头，后跟 JSON- **响应**:

```json

- **流式事件类型**:{

  "translations": {

| type 值 | 说明 | 包含字段 |    "pdf_chk_..._1_5": "翻译文本A",

|---------|------|----------|    "pdf_chk_..._1_6": "翻译文本B"

| `"chunk"` | 中间文本片段 | `content` (String): 部分文本 |  }

| `"step"` | Agent 执行步骤 | `step` (String): 当前步骤描述 |}

| `"final"` | 最终完整结果 | `response` (String): 完整回复文本；`citations` (Array): 引用列表 |```

| `"error"` | 错误 | `error` (String): 错误信息 |

### 划词翻译 (带上下文)

- **错误响应**: 同 4.2（非流式 JSON 格式）翻译任意选中的文本，后端会自动获取 PDF 前几段作为上下文以提高准确度。



---- **接口**: `POST /translate/text`

- **Body**:

### 4.5 获取会话列表```json

{

获取当前用户的所有聊天会话，支持按 PDF 筛选。  "text": "selected text to translate",

  "pdfId": "a1b2c3...", 

- **请求方式**: `GET`  "contextParagraphs": 5 // 可选，上下文段落数

- **请求地址**: `/api/chatbox/sessions`}

- **Query 参数**:```

- **响应**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |```json

|------|------|------|--------|------|{

| `pdfId` | String | 否 | 无 | 按指定 PDF 文件 Hash 筛选 |  "originalText": "...",

| `limit` | Integer | 否 | `50` | 返回数量限制 |  "translatedText": "...",

  "hasContext": true

- **成功响应** (`200`):}

```
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `sessions` | Array | 会话列表 |
| `total` | Integer | 返回的会话数量 |

- **`sessions` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | String | 会话 UUID |
| `pdfId` | String | 关联的 PDF 文件 Hash |
| `title` | String | 会话标题 |
| `createdAt` | String | 创建时间（ISO 8601 格式） |
| `updatedAt` | String | 最后更新时间（ISO 8601 格式） |

---

### 4.6 获取会话历史消息

获取指定会话的所有对话消息。

- **请求方式**: `GET`
- **请求地址**: `/api/chatbox/session/<session_id>/messages`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | String | 会话 UUID |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `sessionId` | String | 会话 ID |
| `messages` | Array | 消息列表 |
| `total` | Integer | 消息总数 |

- **`messages` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 消息 ID |
| `role` | String | 角色：`"user"` 或 `"assistant"` |
| `content` | String | 消息文本内容 |
| `citations` | Array | 引用来源列表（AI 消息有值，用户消息为空数组） |
| `timestamp` | String | 消息创建时间（ISO 8601 格式） |

---

### 4.7 删除会话

删除指定会话及其所有消息。

- **请求方式**: `DELETE`
- **请求地址**: `/api/chatbox/session/<session_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | String | 会话 UUID |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `sessionId` | String | 被删除的会话 ID |
| `message` | String | `"Session deleted"` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `500` | 删除失败或会话不存在 | `{ "error": "<错误信息>" }` |

---

## 5. 高亮标注 (`/api/highlight`)

### 5.1 创建高亮

保存 PDF 上的高亮区域。前端传入像素坐标，后端自动转换为归一化相对坐标（0.0 - 1.0）。

- **请求方式**: `POST`
- **请求地址**: `/api/highlight/`
- **Content-Type**: `application/json`
- **请求参数** (Body):

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `id` | Integer | 高亮记录 ID |
| `rects` | Array | 归一化后的坐标数组，每项含 `x0`, `y0`, `x1`, `y1`（0.0 - 1.0） |
| `message` | String | `"Highlight created"` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 缺少必填字段 | `{ "error": "Missing required fields" }` |
| `404` | 用户书架中无此 PDF | `{ "error": "Paper not in user library" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

---

### 5.2 获取高亮列表

获取某 PDF 的所有高亮，返回归一化坐标，前端需乘以当前 Canvas 尺寸进行渲染。

- **请求方式**: `GET`
- **请求地址**: `/api/highlight/<pdf_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | Integer | 否 | 按页码筛选 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `highlights` | Array | 高亮列表 |
| `total` | Integer | 高亮总数 |

- **`highlights` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 高亮记录 ID |
| `page` | Integer | 所在页码 |
| `rects` | Array | 归一化坐标数组，每项含 `x0`, `y0`, `x1`, `y1` |
| `text` | String | 选中的文本 |
| `color` | String | 高亮颜色 |
| `created_at` | String | 创建时间（ISO 8601 格式） |

---

### 5.3 删除高亮

- **请求方式**: `DELETE`
- **请求地址**: `/api/highlight/<highlight_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `highlight_id` | Integer | 高亮记录 ID |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `500` | 删除失败 | `{ "error": "<错误信息>" }` |

---

### 5.4 更新高亮

- **请求方式**: `PUT`
- **请求地址**: `/api/highlight/<highlight_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `highlight_id` | Integer | 高亮记录 ID |

- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `color` | String | 否 | 新的高亮颜色 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `500` | 更新失败 | `{ "error": "<错误信息>" }` |

---

## 6. 翻译服务 (`/api/translate`)

### 6.1 翻译指定段落

按需翻译 PDF 中的特定段落，支持数据库缓存。后端流程：解析段落 ID → 从 DB 查原文 → 检查缓存 → 调用 LLM 翻译 → 写入 DB。

- **请求方式**: `POST`
- **请求地址**: `/api/translate/paragraph`
- **Content-Type**: `application/json`
- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pdfId` | String | 是 | PDF 文件 Hash |
| `paragraphId` | String | 是 | 段落 ID，格式 `pdf_chk_{hash前缀}_{页码}_{索引}` |
| `force` | Boolean | 否 | 是否强制重新翻译（忽略缓存），默认 `false` |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `translation` | String | 翻译后的中文文本 |
| `cached` | Boolean | 是否命中数据库缓存 |
| `paragraphId` | String | 请求中的段落 ID |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 缺少 `pdfId` 或 `paragraphId` | `{ "error": "Missing pdfId or paragraphId" }` |
| `400` | 段落 ID 格式无效 | `{ "error": "Invalid paragraphId format" }` |
| `404` | 未找到对应段落原文 | `{ "error": "Original text not found for this paragraph" }` |
| `500` | 翻译服务错误 | `{ "error": "<错误信息>" }` |

---

### 6.2 获取整页翻译缓存

批量获取某一页中所有已翻译段落的缓存，适用于页面加载时一次性获取。

- **请求方式**: `GET`
- **请求地址**: `/api/translate/page/<pdf_id>/<page_number>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |
| `page_number` | Integer | 页码 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `pdfId` | String | PDF 文件 Hash |
| `page` | Integer | 页码 |
| `translations` | Object | 键值对，key 为 `paragraphId`，value 为翻译文本。仅包含已翻译的段落 |

---

### 6.3 划词翻译（带上下文）

翻译任意选中的文本。如提供了 `pdfId`，后端会自动从数据库获取 PDF 前几段文本作为上下文以提高翻译准确度。

- **请求方式**: `POST`
- **请求地址**: `/api/translate/text`
- **Content-Type**: `application/json`
- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | String | 是 | 选中的待翻译文本 |
| `pdfId` | String | 否 | 关联 PDF 文件 Hash（用于获取上下文） |
| `contextParagraphs` | Integer | 否 | 上下文段落数，默认 `3` |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `originalText` | String | 原文 |
| `translatedText` | String | 翻译结果 |
| `hasContext` | Boolean | 是否使用了上下文辅助翻译 |
| `contextLength` | Integer | 上下文文本长度（字符数），无上下文时为 `0` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 缺少 `text` 参数 | `{ "error": "Missing text parameter" }` |
| `400` | `text` 为空字符串 | `{ "error": "Text cannot be empty" }` |
| `500` | 翻译服务错误 | `{ "error": "<错误信息>" }` |

---

## 7. 笔记管理 (`/api/notes`)

### 7.1 创建笔记

为指定 PDF 创建一条笔记。

- **请求方式**: `POST`
- **请求地址**: `/api/notes`
- **Content-Type**: `application/json`
- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pdfId` | String | 是 | PDF 文件 Hash |
| `content` | String | 否 | 笔记内容（Markdown 或纯文本） |
| `title` | String | 否 | 笔记标题（如提供，后端将 title + content 合并为 JSON 存储） |
| `keywords` | Array\<String\> | 否 | 关键词列表 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `id` | Integer | 笔记 ID |
| `message` | String | `"Note created"` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `400` | 缺少 `pdfId` | `{ "error": "Missing pdfId" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

---

### 7.2 获取笔记列表

获取用户针对某 PDF 的所有笔记。

- **请求方式**: `GET`
- **请求地址**: `/api/notes/<pdf_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `pdf_id` | String | PDF 文件 Hash |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `notes` | Array | 笔记列表 |
| `total` | Integer | 笔记总数 |

- **`notes` 数组中每个元素**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 笔记 ID |
| `title` | String | 笔记标题（如存储时未设标题则为空字符串） |
| `content` | String | 笔记内容 |
| `keywords` | Array\<String\> | 关键词列表 |
| `createdAt` | String | 创建时间（ISO 8601 格式） |
| `updatedAt` | String | 最后更新时间（ISO 8601 格式） |

---

### 7.3 更新笔记

- **请求方式**: `PUT`
- **请求地址**: `/api/notes/<note_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `note_id` | Integer | 笔记 ID |

- **请求参数** (Body):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | String | 否 | 新笔记内容 |
| `title` | String | 否 | 新标题（如提供，后端将 title + content 合并为 JSON 存储） |
| `keywords` | Array\<String\> | 否 | 新关键词列表 |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `message` | String | `"Note updated"` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `500` | 更新失败 | `{ "error": "<错误信息>" }` |

---

### 7.4 删除笔记

- **请求方式**: `DELETE`
- **请求地址**: `/api/notes/<note_id>`
- **路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `note_id` | Integer | 笔记 ID |

- **成功响应** (`200`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | Boolean | 固定 `true` |
| `message` | String | `"Note deleted"` |

- **错误响应**:

| 状态码 | 条件 | 错误字段 |
|--------|------|----------|
| `404` | 笔记不存在或删除失败 | `{ "error": "Note not found or delete failed" }` |
| `500` | 服务器内部错误 | `{ "error": "<错误信息>" }` |

---

## 8. 通用错误响应格式

所有接口在发生异常时，统一返回以下格式：

| 字段 | 类型 | 说明 |
|------|------|------|
| `error` | String | 错误描述信息 |

鉴权失败时返回 `401`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `error` | String | `"Unauthorized: user identity not resolved"` |
