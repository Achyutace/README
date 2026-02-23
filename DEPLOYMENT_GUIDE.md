# 项目部署指南

---

## 阶段一：当前开发测试部署（开箱即用）

在这个阶段，为了方便快速跑通整个系统，我们使用 Docker Compose 在主服务器上一键启动所有服务，**包括 PostgreSQL 数据库**。

### 部署步骤

1. **准备配置文件**
   在主服务器的项目根目录下，复制配置文件模板：
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **编辑配置**
   打开 `config.yaml`，填入大模型 API 凭证及其他第三方服务密钥。
   *由于使用了测试环境配置，数据库和 Celery 的链接地址无需修改，保持默认（例如指向 `db` 和 `redis`）即可被 Docker 自动接管。*

3. **一键启动**
   使用专为开发阶段准备的 Compose 文件启动：
   ```bash
   docker-compose -f docker-compose.dev.yml up -d --build
   ```

### 如何访问

部署成功后，服务已经在主服务器后台运行。
*   **普通用户访问**：使用浏览器直接打开 `http://<你的主服务器公网IP>:8080` 即可使用完整网站功能。
*   **开发人员本地调试**：本地的 Python 代码若需直连数据库测试，可在自己电脑上的 `config.yaml` 中将数据库的 IP 改为主服务器的公网 IP（需确保主服务器开放了 5432 和 6379 端口）。

---

## 阶段二：未来生产部署（高可用架构）

当项目正式上线，为了保证数据的稳定和安全，我们将不再把数据库跑在容器里，而是使用腾讯云托管的云数据库 PostgreSQL 及 COS 对象存储服务。主服务器上只运行跑核心业务的 Docker 容器。

### 部署步骤

1. **云服务资源**
   *   购买并开通腾讯云 PostgreSQL 实例，记录下内网或公网连接地址及账号密码。
   *   开通腾讯云 COS，获取 SecretId、SecretKey 等凭证。

2. **配置文件**
   在主服务器的项目根目录下：
   ```bash
   cp config.yaml.example config.yaml
   ```

3. **彻底修改配置**
   打开 `config.yaml`，必须填写真实的云端服务信息：
   ```yaml
   database:
     # 填入腾讯云 PostgreSQL 的真实地址
     url: "postgresql://<用户名>:<密码>@<腾讯云DB_IP>:5432/paper_agent_db"
   
   # Celery / Redis 保持默认，由正式版的 docker-compose 内部提供
   celery:
     broker_url: "redis://paper_agent_redis:6379/0"
     result_backend: "redis://paper_agent_redis:6379/1"
   ```
   *别忘了填写其他的 COS、Qdrant 及大模型的配置。*

4. **一键启动**
   使用正式环境的 Compose 文件启动（它不会启动 postgres 容器）：
   ```bash
   docker-compose up -d --build
   ```

### 如何访问

*   **稳定公网访问**：在云防火墙开放主服务器的 **80 端口**。用户直接浏览器访问 `http://<你的主服务器公网IP>` 或绑定的域名即可使用系统。
