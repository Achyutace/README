# 数据库文档

本文档描述 README 项目的数据库架构。项目采用 **PostgreSQL** 作为主要关系型数据库，使用 **Qdrant** 作为向量数据库，并通过 **SQLAlchemy** 进行 ORM 映射。

## 概述

- **关系型数据库**: PostgreSQL
- **向量数据库**: Qdrant
- **ORM**: SQLAlchemy
- **连接管理**: `backend/core/database.py`

### 设计原则

- **全局文件存储**: 相同的 PDF 文件（通过 Hash 识别）在系统中只存储一份物理副本和解析数据 (`global_files`), 不同用户通过 `user_papers` 关联。
- **分离计算与存储**: 复杂的 PDF 解析（段落、图片）只做一次。
- **用户隔离**: 用户数据（笔记、高亮、图谱、对话）严格隔离。

---

## 表结构 (PostgreSQL)

### 1. 用户系统

#### users
存储用户账户信息。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键, default=uuid4 |
| username | String | 用户名 |
| email | String | 邮箱 (Unique) |
| password_hash | String | 密码哈希 |
| created_at | DateTime | 创建时间 |

### 2. 文档管理 (Global)

#### global_files
存储 PDF 文件的物理信息。所有上传同一文件(Hash相同)的用户共享此条目。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| file_hash | String | 主键, SHA256, 全局唯一标识 |
| file_path | String | OSS/S3 存储路径 |
| file_size | Integer | 字节大小 |
| page_count | Integer | 总页数 |
| process_status | String | 状态: PENDING, DONE 等 |
| last_accessed_at | DateTime | 最后访问/引用时间 (用于 GC) |
| metadata_info | JSONB | PDF 元数据 (作者, DOI等) |

#### pdf_paragraphs
存储解析后的段落。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| file_hash | String | FK -> global_files |
| page_number | Integer | 页码 |
| paragraph_index | Integer | 段落在页面的索引 |
| original_text | Text | 原文 |
| translation_text | Text | 翻译 (可选) |
| bbox | JSONB | 坐标 [x,y,w,h] |

#### pdf_images
存储提取的图片信息。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| file_hash | String | FK -> global_files |
| page_number | Integer | 页码 |
| image_index | Integer | 图片索引 |
| bbox | JSONB | 坐标 |
| caption | Text | 图片描述 |

### 3. 用户文献库 (User Library)

#### user_papers
用户与物理文件的关联表。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键 |
| user_id | UUID | FK -> users |
| file_hash | String | FK -> global_files |
| title | String | 用户自定义标题 |
| read_status | String | 'unread', 'reading', 'finished' |
| is_deleted | Boolean | 逻辑删除标记 |
| deleted_at | DateTime | 逻辑删除时间 |
| tags | ARRAY[String] | 标签列表 |
| added_at | DateTime | 添加时间 |
| last_read_at | DateTime | 最后阅读时间 |

#### user_notes
用户对某篇论文的笔记。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| user_paper_id | UUID | FK -> user_papers |
| page_number | Integer | 关联页码 |
| content | Text | 笔记内容 (Markdown) |
| keywords | ARRAY[String] | 关键词/标签 |

#### user_highlights
文本高亮。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| user_paper_id | UUID | FK -> user_papers |
| page_number | Integer | 页码 |
| selected_text | Text | 高亮文本 |
| rects | JSONB | 高亮区域列表 (多行支持) |
| color | String | 颜色 HEX |

### 4. 对话系统 (Chat)

#### chat_sessions
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键 |
| user_id | UUID | FK -> users |
| user_paper_id | UUID | (可选) 关联特定论文 |
| title | String | 会话标题 |

#### chat_messages
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| session_id | UUID | FK -> chat_sessions |
| role | String | 'user' / 'assistant' |
| content | Text | 消息内容 |
| citations | JSONB | 引用列表 (RAG Source) |

### 5. 知识图谱 (Knowledge Graph)

#### user_graph_projects
项目容器。用户可以创建多个图谱项目。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键 |
| user_id | UUID | FK -> users |
| name | String | 项目名称 |
| description | Text | 描述 |

#### graph_nodes
节点表 (关键词/实体)。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键 |
| project_id | UUID | FK -> user_graph_projects |
| label | String | 节点名称 (Label) |
| properties | Text | 属性 (JSON String: color, size...) |

#### graph_edges
边表 (关系)。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | UUID | 主键 |
| project_id | UUID | FK -> user_graph_projects |
| source_node_id | UUID | FK -> graph_nodes |
| target_node_id | UUID | FK -> graph_nodes |
| relation_type | String | 关系类型 (e.g., related_to) |
| description | String | 关系描述 |

#### 关联表 (Link Tables)
- **graph_paper_association**: 项目包含哪些论文。`graph_id` <-> `user_paper_id`
- **paper_node_link**: 论文与节点的关联 (文章提到某关键词)。`user_paper_id` <-> `graph_node_id`
- **note_node_link**: 笔记与节点的关联 (笔记提到某关键词)。`user_note_id` <-> `graph_node_id`

---

## 向量数据库 (Qdrant)

项目默认使用 Qdrant 作为向量存储，用于 RAG 和相关性搜索。

### Collections (集合) 策略

代码实现采用 **Per-File Collection** (分文件集合) 策略，以优化单文档检索性能和物理文件生命周期管理。

#### 命名规则: `paper_{file_hash_prefix}`
每个 PDF 文件对应一个独立的 Collection，名称格式为 `paper_` 加上文件哈希的前16位。

- **Vector Size**: 1536 (OpenAI ada-002 / 3-small)
- **Distance**: Cosine
- **Payload**:
  - `file_hash`: str (完整哈希)
  - `page`: int
  - `section`: str
  - `chunk_index`: int
  - `page_content`: str (文本块内容)

---

## 实体关系与生命周期管理

本项目采用 **软删除 (Soft Delete)** + **延迟垃圾回收 (Garbage Collection)** 的策略来管理文件数据。

### 1. 用户层面 (Logic Delete)
用户"删除"文档时，并不真正删除物理文件或数据库记录，而是标记为已删除。

- **UserPaper 表**:
  - `is_deleted`: `True`
  - `deleted_at`: `Now()`
- **恢复能力**: 支持从"回收站"还原。
- **用户体验**: 误删可恢复。

### 2. 系统层面 (Physical File Retention)
`global_files` 始终保留，直到被系统 GC 清理。

- **去重 (Deduplication)**: 当 User A 删除文件后，User B 如果上传相同文件 (Hash 碰撞)，由于 `global_files` 仍在，可实现"秒传"，无需重新 OCR 和 Vectorize。
- **成本优势**: 存储成本远低于计算 (OCR/Embedding) 成本。

### 3. 垃圾回收策略 (GC Strategy)
系统后台应运行定时任务 (Cron Job)，清理长期无用的 "孤儿文件"。

**清理条件**:
1. 引用计数为 0: 没有任何 `UserPaper` 关联此 `file_hash` (或者所有关联的 `UserPaper` 都已 `is_deleted`)。
2. 冷却期: `last_accessed_at` 在 N 天之前 (如 30 天)。

**清理动作 (Hard Delete)**:
1. 在 PostgreSQL 中删除 `GlobalFile` 记录 (级联删除段落、图片)。
2. 在 Qdrant 中删除对应的 Point。
3. 在 OSS/S3 中删除物理对象。

---