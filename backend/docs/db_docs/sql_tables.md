# SQL 表结构字典

本文档描述 **PostgreSQL** 中的核心表结构。
> - **PK (Primary Key)**: 主键，每行数据的唯一标识符。
> - **FK (Foreign Key)**: 外键，用于关联引用其他表的主键。

## 1. 用户系统 (Users)

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户账户 | `id` (PK), `username`, `email`, `password_hash`, `created_at` |

## 2. 文档存储 (Global Storage)

同一个 PDF 文件在系统中只存一份，通过 Hash 唯一标识。

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `global_files` | PDF 物理文件信息 | `file_hash` (PK), `file_path`, `file_size`, `total_pages`, `metadata_info`, `process_status`, `error_message`, `task_id` |
| `pdf_paragraphs` | 解析后的段落文本 | `id` (PK), `file_hash` (FK), `page_number`, `paragraph_index`, `original_text`, `translation_text`, `bbox` |
| `pdf_images` | 提取的图片 | `id` (PK), `file_hash` (FK), `page_number`, `image_index`, `image_path`, `bbox`, `caption` |

## 3. 用户文献库 (User Library)

用户与文件的关联，支持多对多（不同用户看同一本书）。

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `user_papers` | 用户私有书架 | `id` (PK), `user_id`, `file_hash`, `title`, `read_status`, `is_deleted`, `deleted_at`, `added_at` |
| `user_notes` | 用户笔记 | `id` (PK), `user_paper_id`, `content`, `keywords`, `created_at` |
| `user_highlights` | 文本高亮区域 | `id` (PK), `user_paper_id`, `page_number`, `rects`, `selected_text`, `color`, `created_at` |

## 4. 对话系统 (Chat)

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `chat_sessions` | 对话会话 | `id` (PK), `user_id`, `user_paper_id` (可选), `title`, `updated_at` |
| `chat_messages` | 消息历史 | `id` (PK), `session_id`, `role`, `content`, `citations` (JSON), `created_at` |
| `chat_attachments` | 消息附件 (多媒体/文件) | `id` (PK), `message_id`, `category`, `file_path`, `data` (JSON) |

## 5. 图知识库 (Graph Knowledge)

基于用户的自定义知识图谱构建。

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `user_graph_projects` | 图谱项目空间 | `id` (PK), `user_id`, `name`, `description`, `updated_at` |
| `graph_nodes` | 图节点 | `id` (PK), `project_id`, `label`, `properties` (JSON) |
| `graph_edges` | 图边 (关系) | `id` (PK), `project_id`, `source_node_id`, `target_node_id`, `relation_type`, `description` |
| `graph_paper_association`| 项目与论文关联 (M2M) | `graph_id`, `user_paper_id` |
| `paper_node_link` | 节点与论文引用关联 | `graph_node_id`, `user_paper_id` |
| `note_node_link` | 节点与笔记引用关联 | `graph_node_id`, `user_note_id` |
