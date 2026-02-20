# 生产环境部署指南

将 README 的前端（Vue3 + Nginx）和后端核心业务（Flask + Celery）统一使用 Docker Compose 部署于你的腾讯云服务器上。同时结合腾讯云 PostgreSQL、腾讯云 COS 和 Qdrant Cloud 实现高可用体系。

## 1. 架构总览

*   **云服务器 (应用层)**：腾讯云标准实例。统一运行 `frontend` (Nginx), `backend` (Flask), `celery_worker` (异步引擎) 和 `redis` (消息队列)。
*   **云数据库 (数据层)**：腾讯云 PostgreSQL，持久化结构性业务数据。
*   **对象存储 (文件层)**：腾讯云 COS，存 PDF 物理文件。
*   **向量检索 (AI 层)**：Qdrant Cloud 免费托管版，大模型切片检索 (后续改用腾讯云付费向量存储服务/另买服务器使用部署qdrant)。

---

## 2. 部署前环境准备

1. **准备云服务器并开放端口**：
   - 服务器安装 [Docker](https://docs.docker.com/engine/install/) 和 [Docker Compose](https://docs.docker.com/compose/install/)。
   - 在腾讯云控制台的“安全组”或“防火墙”中，开放服务器的公网 **80** (HTTP) 和 **443** (HTTPS) 端口给全网访问。
2. **云服务凭证**：
   - PostgreSQL 数据库连接地址和账号密码。
   - 腾讯云 COS 的 SecretId、SecretKey、Region 和 Bucket Name。
   - Qdrant Cloud 的集群 URL 和 API Key。
   - 购买的专属域名（在 DNS 控制台将 A 记录解析到这台腾讯云服务器的公网 IP）。

---

## 3. 代码配置

在服务器项目根目录下，复制配置文件模板并进行修改：

```bash
cp config.yaml.example config.yaml
```

按照实际情况修改 `config.yaml` 里的参数：

```yaml
# 1. 配置腾讯云 PostgreSQL (同地域尽量用内网 IP)
database:
  url: "postgresql://<你的用户名>:<你的密码>@<腾讯云DB_IP>:5432/paper_agent_db"

# 2. Redis 保持默认 (Docker 内部解析)
celery:
  broker_url: "redis://paper_agent_redis:6379/0"
  result_backend: "redis://paper_agent_redis:6379/1"

# 3. 配置 Qdrant Cloud (海外节点)
vector_store:
  enable_qdrant: true
  qdrant:
    url: "https://<你的集群id>.eu-central-1-0.aws.cloud.qdrant.io:6333"
    api_key: "<你的API_Key>"
    prefer_grpc: false  # 跨国网络请设为 false 走 HTTP 请求防丢包

# 4. 配置腾讯云 COS
cos:
  enabled: true
  secret_id: "<你的SecretId>"
  ...

# 5. 配置模型凭证与安全
jwt:
  secret: "<自己随便写个复杂字符串>" 
openai:
  api_key: "sk-xxxxxx"  
```

---

## 4. 构建启动

```bash
docker-compose up -d --build
```
*首次运行会非常慢*

启动完毕检查：
```bash
# 所有服务应为 Up 状态
docker-compose ps

# 看看后端有没有连错数据库的各种报错
docker-compose logs -f backend
```

---

## 5. 用户通过浏览器访问？

容器启动后，用户只需在浏览器输入：`http://你的服务器IP` 或者 `http://你的域名`。

---

## 6. 后续处理 (HTTPS 配置)
当系统跑通后，你可以在服务器上安装 Nginx 宿主机服务或使用 [Nginx Proxy Manager](https://nginxproxymanager.com/) 工具为你的域名快速签发免费 SSL 证书，再把流量完整转发进 Docker 的 `80` 端口，实现安全加密传输。
