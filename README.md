# 开发指南

> [!IMPORTANT]
> **本文档仅供本地开发人员调试使用（非 Docker 环境）。**
> 若需在云服务器执行生产或开发阶段的部署，请阅读 [DEPLOYMENT_GUIDE.md](https://github.com/Achyutace/README/blob/main/DEPLOYMENT_GUIDE.md)。

## 开发前说明

> 项目以openapi指导开发，所有接口以openapi定义的为准

* 前端如果需求变动，需要新的接口，需要先修改openapi文档
* 后端根据openapi文档的说明实现接口

## 前端开发

### 联调模式
见后端开发部分。
### mock server模式

> 无需启动后端，使用 Prism 根据 OpenAPI 文档自动生成 Mock 数据。

1. **首次安装全局依赖**
   ```bash
   npm install -g @stoplight/prism-cli
   ```

2. **每次开发**

   2.1 **脚本启动**

   在项目根目录运行一键启动脚本，同时运行 Mock Server 和前端。

   ```bash
   # Windows
   .\start_mock.ps1

   # macOS / Linux
   ./start_mock.sh
   ```

   2.2 **手动启动**

   ```bash
   # 终端 1：启动 Mock Server（在项目根目录下运行指令）
   prism mock docs/openapi/openapi.yaml
   
   # 终端 2：启动前端应用
   cd frontend
   npm install
   npm run dev:mock
   ```
---

## 后端开发

### 0. 准备服务

#### 版本要求

| 组件 | 版本 | 说明 |
|---|---|---|
| **Python** | 3.12 | 启动脚本首次运行时会自动创建虚拟环境，但需系统已安装 Python 3.12 |
| **Node.js** | ≥ 20.19 | Vite 7 要求，推荐使用 Node 20 LTS |
| **Redis** | 任意 | 本地开发用，推荐 ≥ 6.0 |

开发阶段，后端依赖以下云端服务：

1. **PostgreSQL**：推荐使用 [Neon PostgreSQL](https://neon.tech/)。注册并创建一个项目，获取连接字符串。
2.  **Qdrant**：推荐使用 [Qdrant Cloud](https://qdrant.tech/)。注册并创建一个集群，获取 API Key 和集群 URL。
3.  **Llm api**：推荐群里那个。

### 1. 本地启动redis
* **下载**：[Redis-x64-3.2.100.zip](https://github.com/microsoftarchive/redis/releases/tag/win-3.2.100)
* **使用**：解压该压缩包到任意目录，双击运行里面的 `redis-server.exe`，会弹出一个黑色的命令行窗口，上面有端口信息，通常是默认端口6379。开发测试完成后可随时关闭。

### 2. 配置 `config.yaml`

#### 复制配置文件：
```bash
cp config.yaml.example config.yaml
```
#### 填写配置文件：

1. `openai`：大模型服务api。在 `openai` 节点下填写全局 `api_key` 与 `api_base`。如果有针对特定任务（如翻译、视觉）的模型需求，可在 `models` 节点下调整。
2. `postgresql`：关系型数据库，连接到云端（`Neon`）。`database.url`填入云端 PostgreSQL的连接字符串
（示例：`postgresql://<用户名>:<密码>@<云端域名>:5432/<数据库名>?sslmode=require`）
3. `qdrant`：向量存储搜索库。填入云端 Qdrant 服务的 `url` 与 `api_key`。
4. `celery`：依赖 Redis 作为 Broker 和 Result Backend，按照步骤一的结果填写，通常不用修改。
5. `Semantic Scholar`, `Tavily`：ss可以无api请求，申请api可放宽限流；tavily需要申请api，有免费月额度。
6. `jwt`：用户鉴权设置。
7. `cos`：文档图片的存储。通过配置 `enabled: false` 可关闭云端存储并自动映射到本地 `storage/` 文件夹。

### 3. 启动
#### 3.1 脚本启动
> 脚本首次运行时会自动创建 Python 3.12 虚拟环境并安装依赖，无需手动操作。

**先决条件**：
- [安装 Redis](https://redis.io/download/)。
- 将解压后redis所在的文件夹添加到环境变量，确保在命令行能直接执行 `redis-server`。
- 如果是 Windows，请确保 `Python 3.12`、`Node.js`、`Redis` 的路径都在环境变量中。

在项目根目录下打开终端，直接运行：

```bash
# Windows (PowerShell)
.\start_full.ps1

# macOS / Linux (Terminal)
./start_full.sh
```

#### 3.2 手动启动

0. 数据库同步
   > **注意**：初次拉取或他人更新了数据库代码时必须执行。一键启动脚本（`start_full`）会自动执行此步骤。

   ```bash
   cd backend
   # 激活虚拟环境
   conda activate readme  
   # 数据库更新
   flask db upgrade
   ```

1. 后端 api 启动
   ```bash
   cd backend

   # 0. 创建虚拟环境
   conda create -n readme python=3.12

   # 1. 激活虚拟环境
   conda activate readme  

   # 2. 安装依赖
   pip install -r requirements.txt

   # 3. 启动主后端应用
   python app.py
   ```
2. celery 启动
   > 注意：需要先启动redis。
   ```bash
   # 新开一个终端
   cd backend
   celery -A celery_app worker --loglevel=info --pool=solo
   ```
3. 前端 ui 启动
   ```bash
   cd frontend
   npm run dev
   ```

### 4. 接口调试说明
后端启动后，可利用`swagger ui`越过前端直接在浏览器发送真实请求：
- **调试地址**: `http://localhost:5000/api/docs`
- **说明**：此页面同步 OpenAPI 文档。

### 5. 数据库更新

如果在开发过程中修改了后端模型代码(`backend/model/` 目录下)时，需要手动同步数据库结构：

```bash
cd backend
# 1. 激活虚拟环境
conda activate readme

# 2. 生成迁移脚本 (会在 backend/migrations/versions 下生成一个新的 py 文件)
flask db migrate -m "描述你的变更，例如：add_user_phone_field"

# 3. 将变更应用到数据库
flask db upgrade
```

> [!IMPORTANT]
> 在提交 Git 代码时，必须将 `backend/migrations/versions/` 下新生成的迁移脚本一并提交。

---
