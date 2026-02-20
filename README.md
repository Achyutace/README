# README

## 快速开始 (本地开发指南)

项目后端强依赖多种云服务，不同情况下提供不同的开发方案：

### 纯前端

> 无需启动后端，使用 Prism 根据 OpenAPI 文档自动生成 Mock 数据。

1. **安装全局依赖**：
   ```bash
   npm install -g @stoplight/prism-cli
   ```

**每次开发：** 可以在项目根目录运行一键启动脚本（脚本会同时启动 Mock Server 和前端）：

```bash
# Windows
.\start_mock.ps1

# macOS / Linux
./start_mock.sh
```

> **注意**：如果不想使用脚本，也可以分别在两个终端手动运行：

```bash
# 终端 1：启动 Mock Server（项目根目录）
   prism mock docs/openapi/openapi.yaml
   
   # 终端 2：启动前端应用
   cd frontend
   npm install
   npm run dev:mock
```

> **联调说明**：前端联调，连接真实后端服务时，将 `frontend/.env` 中的 `VITE_API_BASE_URL` 指向部署好的后端域名，然后运行 `npm run dev` 即可。

---

### 后端 / 全栈开发

> 需完整运行 Python 服务。由于后端依赖云资源，联系相关人员获取公共测试环境的 `config.yaml` 配置文件（不要使用线上正式环境）。

**前提：** 将配置好的 `config.yaml` 放入项目根目录。

**启动后端主服务：**

#### 选项一：手动使用 Conda 启动

```bash
# Windows / macOS / Linux
cd backend
conda create -n readme python=3.10 -y
conda activate readme
pip install -r requirements.txt
python app.py
```

#### 选项二：使用全栈一键启动脚本

由于项目包含前后端服务，可以在项目根目录运行全栈一键启动脚本（脚本会自动管理 venv 环境和依赖，并同时启动前后端）：

```bash
# Windows
.\start_full.ps1

# macOS / Linux
./start_full.sh
```

> **注意**：服务启动在 `http://localhost:5000`，需同时（新建终端）启动 Celery Worker：

```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

---
