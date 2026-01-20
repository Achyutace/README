# README

## 运行指南

请按照以下步骤分别启动后端和前端服务。

### 1. 后端启动 (Backend)

建议使用 Python 3.10+ 环境。

#### Windows
```powershell
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

#### macOS / Linux
```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python3 app.py
```

---

### 2. 前端启动 (Frontend)

需要安装 [Node.js](https://nodejs.org/) (推荐 v18+)。

#### 所有系统 (Windows/macOS/Linux)
```bash
# 进入前端目录
cd frontend

# 安装依赖 (如果尚未安装)
npm install

# 启动开发服务器
npm run dev
```

---

