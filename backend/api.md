# 后端接口文档

## 1. 基础说明

*   **Base URL**: `/api`
*   **协议**: HTTP / SSE (Server-Sent Events)
*   **数据格式**: JSON
*   **鉴权/用户隔离**:
    *   后端通过 Header 或 Query Parameter 识别用户。
    *   **Header**: `X-User-Id` (推荐)
    *   **Query**: `?userId=xxx`
    *   若未提供，默认为 `default_user`。

---

## 2. 系统接口 (System)

### 2.1 健康检查
用于前端检测后端服务状态及各组件（数据库、RAG、翻译服务）的连接情况。

*   **接口地址**: `/api/health`
*   **请求方式**: `GET`
*   **响应示例**:
    ```json
    {
      "status": "ok",
      "user_id": "current_user_id",
      "services": {
        "storage": true,
        "rag": true,
        "translate": true,
        "agent": true
      }
    }
    ```

---

## 3. PDF 文件管理 (PDF Management)

**Base Path**: `/api/pdf`

### 3.1 上传 PDF
上传文件，计算 Hash，同步解析段落，并触发后台异步数据库存储和 RAG 索引任务。

*   **接口地址**: `/upload`
*   **请求方式**: `POST`
*   **Content-Type**: `multipart/form-data`
*   **请求参数**:
    *   `file`: (File, 必填) PDF 文件对象。
*   **响应示例**:
    ```json
    {
      "id": "file_hash_value",          // PDF 的唯一标识 (pdfId)
      "fileHash": "file_hash_value",
      "filename": "paper.pdf",
      "pageCount": 10,
      "userId": "user_123",
      "status": "processing",           // 标识后台正在进行 RAG 索引
      "isNewUpload": true,              // false 表示秒传
      "paragraphs": [                   // 解析出的段落结构
        {
          "id": "pdf_chk_hash_1_0",
          "content": "Abstract...",
          "page": 1,
          "bbox": [10, 20, 100, 200]
        }
      ]
    }
    ```

### 3.2 获取 PDF 元数据
*   **接口地址**: `/<pdf_id>/info`
*   **请求方式**: `GET`
*   **响应示例**:
    ```json
    {
      "filename": "paper.pdf",
      "page_count": 10,
      "upload_time": "2023-10-01..."
    }
    ```

### 3.3 获取 PDF 文本内容
*   **接口地址**: `/<pdf_id>/text`
*   **请求方式**: `GET`
*   **Query 参数**:
    *   `page`: (Int, 可选) 指定页码。
*   **响应示例**:
    ```json
    {
      "text": "提取的纯文本内容..."
    }
    ```

---

## 4. AI 对话 (Chatbox)

**Base Path**: `/api/chatbox`

### 4.1 发送消息 (非流式)
等待 AI 生成完整回答后一次性返回。

*   **接口地址**: `/message`
*   **请求方式**: `POST`
*   **请求 Body**:
    ```json
    {
      "message": "这篇文章的主要贡献是什么？",
      "pdfId": "必填，当前关联的 PDF ID",
      "userId": "可选，用户ID",
      "history": [  // 完整的对话历史
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，请问有什么可以帮您？"}
      ]
    }
    ```
*   **响应示例**:
    ```json
    {
      "response": "这篇文章的主要贡献是...",
      "citations": ["引用来源1", "引用来源2"],
      "steps": ["思考步骤1", "检索工具调用..."]
    }
    ```

### 4.2 发送消息 (流式 SSE)
用于实现打字机效果。

*   **接口地址**: `/stream`
*   **请求方式**: `POST`
*   **Content-Type**: `application/json`
*   **响应 Content-Type**: `text/event-stream`
*   **请求 Body**: 同 4.1 接口。
*   **流式事件结构**:
    *   数据格式为 `data: {JSON}\n\n`
    *   **事件类型 (type)**:
        *   `step`: 中间思考步骤或工具调用。
        *   `final`: 最终回答的片段（需前端拼接）。
        *   `error`: 发生错误。
*   **流式数据示例**:
    ```text
    data: {"type": "step", "content": "正在检索相关段落..."}
    
    data: {"type": "final", "content": "这篇"}
    
    data: {"type": "final", "content": "文章"}
    ```

---

## 5. 高亮标注 (Highlight)

**Base Path**: `/api/highlight`

### 5.1 创建高亮
前端传入 PDF.js 获取的绝对坐标，后端自动归一化存储。

*   **接口地址**: `/`
*   **请求方式**: `POST`
*   **请求 Body**:
    ```json
    {
      "pdfId": "file_hash_value",
      "page": 1,
      "text": "选中的文本内容",
      "color": "#FFFF00", // 可选，默认黄色
      "comment": "这是一个重要的结论", // 可选
      "pageWidth": 800,   // 当前 Canvas 宽度 (用于坐标归一化)
      "pageHeight": 1200, // 当前 Canvas 高度
      "rects": [          // PDF.js getClientRects() 的原始数据
        {"x": 100, "y": 100, "width": 50, "height": 20}
      ]
    }
    ```
*   **响应示例**:
    ```json
    {
      "success": true,
      "id": 123,
      "rects": [ ... ] // 归一化后的相对坐标 (0.0-1.0)
    }
    ```

### 5.2 获取某 PDF 的所有高亮
*   **接口地址**: `/<pdf_id>`
*   **请求方式**: `GET`
*   **Query 参数**:
    *   `page`: (Int, 可选) 按页码筛选。
*   **响应示例**:
    ```json
    [
      {
        "id": 123,
        "page": 1,
        "bbox": {
            "union": {"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.2}, // 相对坐标
            "rects": [...]
        },
        "color": "#FFFF00",
        "comment": "注释内容",
        "text": "高亮文本"
      }
    ]
    ```

### 5.3 更新高亮
*   **接口地址**: `/<highlight_id>`
*   **请求方式**: `PUT`
*   **请求 Body**:
    ```json
    {
      "color": "#FF0000",
      "comment": "更新后的注释"
    }
    ```

### 5.4 删除高亮
*   **接口地址**: `/<highlight_id>`
*   **请求方式**: `DELETE`

---

## 6. 翻译服务 (Translate)

**Base Path**: `/api/translate`

### 6.1 翻译指定段落
按需触发翻译，支持缓存。

*   **接口地址**: `/paragraph`
*   **请求方式**: `POST`
*   **请求 Body**:
    ```json
    {
      "pdfId": "file_hash_value",
      "paragraphId": "pdf_chk_xxxx_1_5", // 格式: pdf_chk_{前缀}_{页码}_{索引}
      "force": false // 是否强制重新翻译（忽略缓存）
    }
    ```
*   **响应示例**:
    ```json
    {
      "success": true,
      "paragraphId": "pdf_chk_xxxx_1_5",
      "translation": "这是翻译后的中文内容...",
      "cached": true // 是否命中了数据库缓存
    }
    ```

### 6.2 获取某页的所有历史翻译
用于页面加载或刷新时，批量获取该页已存在的翻译记录。

*   **接口地址**: `/page/<pdf_id>/<int:page_number>`
*   **请求方式**: `GET`
*   **响应示例**:
    ```json
    {
      "pdfId": "...",
      "page": 1,
      "translations": {
        "pdf_chk_xxxx_1_0": "第一段的翻译",
        "pdf_chk_xxxx_1_5": "第五段的翻译"
      }
    }
    