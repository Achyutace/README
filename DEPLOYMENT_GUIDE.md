# 项目部署指南
---

该文档指导**云服务器**上的 Docker 化部署。

## 开发测试部署 (Docker + 云端 DB + 本地 COS)

核心服务跑在 Docker 中，数据库等重型中间件直接连接云端。

### 架构概览
- **Docker 容器**：Redis, Celery Worker, Backend (API), Frontend (Nginx)。
- **云端服务**：SQL (PostgreSQL) 与 Qdrant (向量库) 均连接云服务。
- **对象存储 (COS)**：通过挂载云服务器本地目录 `storage/` 来模拟。

### 部署步骤

1. **准备配置文件**
   在主服务器的项目根目录下：
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **编辑配置**
   打开 `config.yaml`，填入：
   - `openai`: API 凭证。
   - `database.url`: 云端 PostgreSQL 连接串。
   - `vector_store.qdrant`: 云端 Qdrant 地址与 Key。
   - `cos.enabled`: 保持 `false`（启用本地模拟挂载模式）。
   - `celery`: 保持 `redis://redis:6379/...`（容器内互联）。

3. **一键启动**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d --build
   ```

4. **确认迁移**
   开发环境默认会自动尝试执行 `flask db upgrade`。如果数据库开启了保护或自动执行失败，可手动触发：
   ```bash
   docker exec -it paper_agent_backend_dev flask db upgrade
   ```

### 如何访问
- **普通用户**：`http://<服务器公网IP>:8080`
- **文件存储**：上传的 PDF 或附件将保存在服务器的 `./storage` 目录下。

---

## 生产部署

当项目正式上线，所有持久化内容（数据库、文档存储）均切换为高可用云原生方案。

### 架构概览
- **Docker 容器**：核心服务逻辑。
- **数据库**：使用高可用版云 PostgreSQL 服务。
- **向量库**：Qdrant 云服务（可能根据流量需求独立部署或扩充）。
- **对象存储 (COS)**：切换到真实的腾讯云 COS。

### 部署步骤

1. **配置文件**
   编辑 `config.yaml`，必须切换生产级配置：
   ```yaml
   app:
     env: "production"

   database:
     url: "postgresql://<生产环境数据库地址>"

   cos:
     enabled: true # 切换到正式 COS
     secret_id: "..."
     secret_key: "..."
     # ...其他 COS 必填项
   ```

2. **一键启动**
   使用生产环境 Compose 文件：
   ```bash
   docker-compose up -d --build
   ```

3. **数据库迁移 (手动执行)**
   为了确保生产数据安全，系统不会在启动时自动执行迁移。如有数据库结构更新，请按以下步骤操作：
   - **备份**：在执行前，先在云数据库控制台（如 Neon）创建一个快照。
   - **检查**：在本地检查 `backend/migrations/versions/` 下的新脚本，确保没有非预期的 `drop_table` 或 `drop_column` 指令。
   - **执行**：
     ```bash
     docker exec -it paper_agent_backend flask db upgrade
     ```

### 如何访问
- **标准访问**：在防火墙开放 **80 端口**。访问 `http://<服务器公网IP>`。
- **安全性**：由于启用了云端 COS，服务器本地硬盘不再存储业务敏感文档。

