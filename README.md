# README

## 前端开发

> 无需启动后端，使用 Prism 根据 OpenAPI 文档自动生成 Mock 数据。

```bash
npm install -g @stoplight/prism-cli
```

**每次开发：** 分别在两个终端运行：

```bash
# 终端 1：启动 Mock Server（项目根目录）
prism mock docs/openapi/openapi.yaml

# 终端 2：启动前端
cd frontend && npm install && npm run dev:mock
```

联调阶段（后端已部署），修改 `frontend/.env.production` 中的域名后运行 `npm run dev` 即可。

---

## 后端开发

**前提：** Python 3.10+，以及获取 `config.yaml`（含云服务连接信息，不入库）。

```bash
# Windows
cd backend
python -m venv venv && .\venv\Scripts\activate
pip install -r requirements.txt
python app.py

# macOS / Linux
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

服务启动在 `http://localhost:5000`，需同时启动 Celery Worker：

```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

---
