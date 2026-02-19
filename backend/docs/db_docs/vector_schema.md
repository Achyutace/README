# 向量数据库设计 (Qdrant)

用于支持 RAG (检索增强生成) 与语义搜索。

## Collection 策略: Per-File

为了优化单文档检索性能和物理清理，每个 PDF 文件对应一个独立的 Collection。

**命名规则**: `paper_{file_hash_prefix}` (取 file_hash 的前16位)

## 向量配置

- **维度 (Size)**: 1536 (OpenAI ada-002 / 3-small 标准)
- **距离度量**: Cosine

## Payload 结构

存储在向量旁边的元数据，用于过滤和上下文构建。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `file_hash` | Keyword | 完整的文件 SHA256 Hash |
| `user_ids` | List<Keyword> | 有权限访问此文档的用户 ID 列表 |
| `page` | Integer | 页码 |
| `chunk_index` | Integer | 切片序号 |
| `section` | Keyword | 内容所属区域 (默认为 content) |
| `page_content` | Text | 实际的文本内容 |
