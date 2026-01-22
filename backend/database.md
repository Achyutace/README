# 数据库文档

本文档描述 README 项目的 SQLite 数据库结构、表关系和使用方式。

## 概述

数据库使用 SQLite，通过 `models/database.py` 中的 `Database` 类进行管理。数据库文件存储在 `storage/users/{user_id}/data.db`。

### 主要特性

- **外键约束**：启用 `PRAGMA foreign_keys = ON`，支持级联删除
- **文件哈希**：使用 SHA256 哈希作为 PDF 文件的唯一标识
- **JSON 存储**：复杂数据（bbox、metadata、citations 等）以 JSON 字符串存储在 TEXT 字段中
- **时间戳**：所有表都包含创建/更新时间戳

---

## 表结构

### 1. pdf_files - PDF 文件表

存储上传的 PDF 文件基本信息。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| file_hash | TEXT | UNIQUE NOT NULL | 文件 SHA256 哈希值 |
| filename | TEXT | NOT NULL | 原始文件名 |
| file_path | TEXT | NOT NULL | 文件存储路径 |
| user_id | TEXT | | 上传用户 ID |
| page_count | INTEGER | | PDF 页数 |
| file_size | INTEGER | | 文件大小（字节） |
| upload_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 上传时间 |
| last_access_time | TIMESTAMP | | 最后访问时间 |
| metadata | TEXT | | JSON 格式的元数据 |

**索引**：`file_hash` (UNIQUE)

---

### 2. pdf_paragraphs - PDF 段落表

存储 PDF 文档的段落文本和翻译。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| file_hash | TEXT | NOT NULL, FK | 关联的 PDF 文件哈希 |
| page_number | INTEGER | NOT NULL | 页码（从 1 开始） |
| paragraph_index | INTEGER | NOT NULL | 段落在页面中的索引 |
| original_text | TEXT | NOT NULL | 原文内容 |
| translation_text | TEXT | | 翻译内容 |
| bbox | TEXT | | JSON 格式的边界框坐标 `[x0, y0, x1, y1]` |
| created_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**约束**：
- FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE
- UNIQUE(file_hash, page_number, paragraph_index)

**索引**：
- `idx_paragraphs_file_hash` ON (file_hash)
- `idx_paragraphs_page` ON (file_hash, page_number)

---

### 3. pdf_images - PDF 图片表

存储从 PDF 中提取的图片信息。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| file_hash | TEXT | NOT NULL, FK | 关联的 PDF 文件哈希 |
| page_number | INTEGER | NOT NULL | 页码 |
| image_index | INTEGER | NOT NULL | 图片在页面中的索引 |
| image_path | TEXT | NOT NULL | 图片文件存储路径 |
| image_format | TEXT | | 图片格式（png, jpg 等） |
| width | INTEGER | | 图片宽度（像素） |
| height | INTEGER | | 图片高度（像素） |
| file_size | INTEGER | | 图片文件大小（字节） |
| bbox | TEXT | | JSON 格式的边界框坐标 |
| extracted_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 提取时间 |

**约束**：
- FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE
- UNIQUE(file_hash, page_number, image_index)

**索引**：
- `idx_images_file_hash` ON (file_hash)
- `idx_images_page` ON (file_hash, page_number)

---

### 4. user_notes - 用户笔记表

存储用户的 PDF 笔记。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| file_hash | TEXT | NOT NULL, FK | 关联的 PDF 文件哈希 |
| user_id | TEXT | NOT NULL | 用户 ID |
| page_number | INTEGER | | 关联的页码（可选） |
| note_content | TEXT | NOT NULL | 笔记内容 |
| note_type | TEXT | DEFAULT 'general' | 笔记类型 |
| color | TEXT | DEFAULT '#FFEB3B' | 笔记颜色 |
| position | TEXT | | JSON 格式的位置信息 |
| created_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**约束**：
- FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE

**索引**：
- `idx_notes_file_user` ON (file_hash, user_id)

---

### 5. user_highlights - 用户高亮表

存储用户的 PDF 文本高亮。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| file_hash | TEXT | NOT NULL, FK | 关联的 PDF 文件哈希 |
| user_id | TEXT | NOT NULL | 用户 ID |
| page_number | INTEGER | NOT NULL | 页码 |
| highlighted_text | TEXT | NOT NULL | 高亮的文本内容 |
| color | TEXT | DEFAULT '#FFFF00' | 高亮颜色 |
| bbox | TEXT | NOT NULL | JSON 格式的边界框坐标 |
| comment | TEXT | | 高亮注释 |
| created_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**约束**：
- FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE

**索引**：
- `idx_highlights_file_user` ON (file_hash, user_id)

---

### 6. chat_sessions - 聊天会话表

存储用户的聊天会话。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| session_id | TEXT | UNIQUE NOT NULL | 会话 UUID |
| user_id | TEXT | NOT NULL | 用户 ID |
| file_hash | TEXT | FK | 关联的 PDF 文件哈希（可选） |
| title | TEXT | | 会话标题 |
| created_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 最后更新时间 |

**约束**：
- FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE SET NULL

**索引**：
- `idx_chat_sessions_user` ON (user_id, updated_time DESC)

---

### 7. chat_messages - 聊天消息表

存储聊天会话中的消息。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| session_id | TEXT | NOT NULL, FK | 关联的会话 ID |
| role | TEXT | NOT NULL | 消息角色（user/assistant） |
| content | TEXT | NOT NULL | 消息内容 |
| citations | TEXT | | JSON 格式的引用信息 |
| created_time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**约束**：
- FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE

**索引**：
- `idx_chat_messages_session` ON (session_id, created_time)

---

## 表关系图

```
pdf_files (file_hash)
    │
    ├──< pdf_paragraphs (file_hash) [CASCADE]
    │
    ├──< pdf_images (file_hash) [CASCADE]
    │
    ├──< user_notes (file_hash) [CASCADE]
    │
    ├──< user_highlights (file_hash) [CASCADE]
    │
    └──< chat_sessions (file_hash) [SET NULL]
              │
              └──< chat_messages (session_id) [CASCADE]
```

**级联删除规则**：
- 删除 `pdf_files` 记录时，自动删除关联的 paragraphs、images、notes、highlights
- 删除 `pdf_files` 时，关联的 `chat_sessions.file_hash` 设为 NULL（保留会话）
- 删除 `chat_sessions` 记录时，自动删除关联的 messages

---

## 常用操作示例

### PDF 文件操作

```python
from models.database import Database

db = Database('storage/users/default/data.db')

# 添加 PDF 文件
file_hash = db.add_pdf_file(
    file_path='/path/to/file.pdf',
    filename='paper.pdf',
    user_id='user123',
    page_count=10
)

# 检查文件是否存在
exists = db.check_pdf_exists(file_hash)

# 获取文件信息
pdf_info = db.get_pdf_file(file_hash)

# 列出用户的 PDF 文件
pdf_list = db.list_pdf_files(user_id='user123', limit=20)

# 删除 PDF 文件（级联删除所有关联数据）
stats = db.delete_pdf_file(file_hash)
```

### 段落操作

```python
# 添加段落
db.add_paragraph(
    file_hash=file_hash,
    page_number=1,
    paragraph_index=0,
    original_text='This is the original text.',
    bbox={'x0': 50, 'y0': 100, 'x1': 550, 'y1': 120}
)

# 批量添加段落
paragraphs = [
    {'page': 1, 'index': 0, 'content': 'First paragraph'},
    {'page': 1, 'index': 1, 'content': 'Second paragraph'},
]
db.add_paragraphs_batch(file_hash, paragraphs)

# 更新翻译
db.update_paragraph_translation(
    file_hash=file_hash,
    page_number=1,
    paragraph_index=0,
    translation_text='这是原文的翻译。'
)

# 获取某页的段落
paragraphs = db.get_paragraphs(file_hash, page_number=1)

# 获取完整文本
full_text = db.get_full_text(file_hash, include_translation=True)
```

### 笔记操作

```python
# 添加笔记
note_id = db.add_note(
    file_hash=file_hash,
    user_id='user123',
    note_content='This is important!',
    page_number=5,
    color='#FF5722'
)

# 更新笔记
db.update_note(note_id, note_content='Updated note content')

# 获取用户的笔记
notes = db.get_notes(file_hash, user_id='user123')

# 删除笔记
db.delete_note(note_id)
```

### 高亮操作

```python
# 添加高亮
highlight_id = db.add_highlight(
    file_hash=file_hash,
    user_id='user123',
    page_number=3,
    highlighted_text='important concept',
    bbox={'x0': 100, 'y0': 200, 'x1': 300, 'y1': 220},
    color='#FFFF00',
    comment='Remember this!'
)

# 获取高亮
highlights = db.get_highlights(file_hash, user_id='user123', page_number=3)

# 删除高亮
db.delete_highlight(highlight_id)
```

### 聊天会话操作

```python
import uuid

# 创建会话
session_id = str(uuid.uuid4())
db.create_chat_session(
    session_id=session_id,
    user_id='user123',
    file_hash=file_hash,
    title='关于论文的讨论'
)

# 添加消息
db.add_chat_message(session_id, role='user', content='这篇论文的主要观点是什么？')
db.add_chat_message(
    session_id,
    role='assistant',
    content='这篇论文主要讨论了...',
    citations=[{'page': 1, 'text': '引用内容'}]
)

# 获取会话消息
messages = db.get_chat_messages(session_id)

# 获取聊天历史（用于上下文）
history = db.get_chat_history(session_id, limit=10)

# 列出用户会话
sessions = db.list_chat_sessions(user_id='user123')

# 更新会话标题
db.update_chat_session_title(session_id, '新标题')

# 删除会话
deleted_count = db.delete_chat_session(session_id)
```

---

## 数据存储位置

```
storage/
├── users/
│   └── {user_id}/
│       ├── data.db          # SQLite 数据库文件
│       ├── uploads/         # 上传的 PDF 文件
│       └── cache/           # 缓存文件
├── images/                  # 提取的图片
└── chroma_db/              # 向量数据库（RAG）
```

---

## 注意事项

1. **文件哈希**：使用 `Database.calculate_file_hash()` 或 `Database.calculate_stream_hash()` 计算文件哈希
2. **JSON 字段**：`bbox`、`metadata`、`position`、`citations` 等字段存储 JSON 字符串，读取时需要 `json.loads()` 解析
3. **用户隔离**：所有数据通过 `user_id` 进行用户隔离
4. **级联删除**：删除 PDF 文件会自动清理关联的段落、图片、笔记、高亮数据
5. **事务**：批量操作使用事务，失败时会回滚
