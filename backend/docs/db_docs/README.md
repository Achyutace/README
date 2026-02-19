# 数据库架构概览

## 架构原则
1.  **全局单例 (Global Singleton)**: PDF 文件按 Hash 存储在 `global_files`，所有用户共享一份物理文件和解析数据。
2.  **软删除 (Soft Delete)**: 用户移除论文仅标记 `is_deleted=True`，物理清理通过后台 GC 任务执行。
3.  **读写分离**: 
    - 结构化数据 (用户、笔记、元数据) -> **PostgreSQL**
    - 非结构化检索 (RAG 向量) -> **Qdrant**

## 快速导航
- [实体关系图 (ER Diagram)](./schema/er_diagram.mermaid)
- [SQL 表结构字典](./schema/sql_tables.md)
- [向量集合策略](./schema/vector_schema.md)
