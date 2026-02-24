#!/bin/bash

# README PDF Reader - Full Stack Start Script (Linux / macOS)
# 用法: 在项目根目录下运行  ./start_full.sh

set -e

# ==================== 颜色定义 ====================
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m'

# ==================== 路径定义 ====================
# 使用脚本所在目录，而不是 pwd（避免在别处调用脚本时出错）
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON_EXE="$BACKEND_DIR/venv/bin/python"
PIP_EXE="$BACKEND_DIR/venv/bin/pip"
FLASK_EXE="$BACKEND_DIR/venv/bin/flask"
CELERY_EXE="$BACKEND_DIR/venv/bin/celery"

# 用于记录各子进程 PID
PIDS=()
REDIS_STARTED_BY_US=false

echo -e "${CYAN}===============================================${NC}"
echo -e "${CYAN}   Starting README PDF Reader Full Stack Core   ${NC}"
echo -e "${CYAN}===============================================${NC}"

# ==================== 清理函数 ====================
cleanup() {
    echo -e "\n${YELLOW}Gracefully stopping all services...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo -e "  ${GRAY}Stopped process PID $pid${NC}"
        fi
    done
    if $REDIS_STARTED_BY_US; then
        pkill -f "redis-server" 2>/dev/null || true
        echo -e "  ${GRAY}Stopped redis-server${NC}"
    fi
    echo -e "${GREEN}All services stopped. Happy coding!${NC}"
    exit 0
}
trap cleanup INT TERM

# ==================== 1. 检查并启动 Redis ====================
echo -e "\n${YELLOW}[Stage 1/5] Checking Redis service...${NC}"

if nc -z localhost 6379 2>/dev/null; then
    echo -e "  ${GREEN}Redis is already running (Port 6379), skipping.${NC}"
else
    echo -e "  ${GRAY}Redis not detected on port 6379. Searching for binary...${NC}"
    if command -v redis-server &>/dev/null; then
        echo -e "  ${GRAY}Starting redis-server in background...${NC}"
        redis-server --daemonize yes
        REDIS_STARTED_BY_US=true
        sleep 1
        if nc -z localhost 6379 2>/dev/null; then
            echo -e "  ${GREEN}Redis started successfully.${NC}"
        else
            echo -e "  ${RED}WARNING: Redis started but port 6379 not responding.${NC}"
        fi
    else
        echo -e "  ${RED}WARNING: redis-server not found in PATH.${NC}"
        echo -e "  ${GRAY}Please start Redis manually or install it first.${NC}"
    fi
fi

# ==================== 2. 后端环境准备 ====================
echo -e "\n${YELLOW}[Stage 2/5] Preparing backend environment...${NC}"

# 2a. 创建虚拟环境
if [ ! -f "$PYTHON_EXE" ]; then
    echo -e "  ${GRAY}Virtual environment not found. Creating with Python 3.12...${NC}"
    if ! command -v python3.12 &>/dev/null; then
        echo -e "  ${RED}ERROR: Python 3.12 not found.${NC}"
        echo -e "  ${GRAY}  macOS : brew install python@3.12${NC}"
        echo -e "  ${GRAY}  Ubuntu: sudo apt install python3.12 python3.12-venv${NC}"
        exit 1
    fi
    PY_VER=$(python3.12 --version 2>&1)
    echo -e "  ${GREEN}Detected: $PY_VER${NC}"

    echo -e "  ${GRAY}Creating virtual environment at $BACKEND_DIR/venv ...${NC}"
    python3.12 -m venv "$BACKEND_DIR/venv"
    if [ ! -f "$PYTHON_EXE" ]; then
        echo -e "  ${RED}ERROR: Failed to create virtual environment.${NC}"
        echo -e "  ${GRAY}On Ubuntu/Debian you may need: sudo apt install python3.12-venv${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}Virtual environment created.${NC}"
fi

# 2b. 安装 Python 依赖
echo -e "  ${GRAY}Installing Python dependencies...${NC}"
"$PIP_EXE" install -r "$BACKEND_DIR/requirements.txt" --quiet
echo -e "  ${GREEN}Dependencies ready.${NC}"

# 2c. 数据库迁移（在 backend 目录下执行）
echo -e "  ${GRAY}Syncing database schema (flask db upgrade)...${NC}"
cd "$BACKEND_DIR"
export FLASK_APP=app.py
if "$FLASK_EXE" db upgrade 2>&1; then
    echo -e "  ${GREEN}Database sync successful.${NC}"
else
    echo -e "  ${YELLOW}WARNING: Database sync failed or already up to date.${NC}"
fi

# ==================== 3. 启动后端服务 ====================
echo -e "\n${YELLOW}[Stage 3/5] Starting backend services...${NC}"

# 3a. 启动 Backend API（在 backend 目录下运行）
echo -e "  ${GRAY}Starting Backend API (python app.py)...${NC}"
cd "$BACKEND_DIR"
"$PYTHON_EXE" app.py &
API_PID=$!
PIDS+=($API_PID)

# 等待几秒，检查是否立即崩溃
sleep 3
if ! kill -0 $API_PID 2>/dev/null; then
    echo -e "  ${RED}ERROR: Backend API exited immediately.${NC}"
    echo -e "  ${YELLOW}Run 'cd backend && python app.py' manually to see errors.${NC}"
    cleanup
    exit 1
fi
echo -e "  ${GREEN}Backend API started (PID $API_PID).${NC}"

# 3b. 启动 Celery Worker（在 backend 目录下运行）
echo -e "  ${GRAY}Starting Celery Worker...${NC}"
cd "$BACKEND_DIR"
"$CELERY_EXE" -A celery_app worker --loglevel=info --pool=solo &
CELERY_PID=$!
PIDS+=($CELERY_PID)
echo -e "  ${GREEN}Celery Worker started (PID $CELERY_PID).${NC}"

# ==================== 4. 启动前端服务 ====================
echo -e "\n${YELLOW}[Stage 4/5] Starting frontend service...${NC}"

cd "$FRONTEND_DIR"

echo -e "  ${GRAY}Checking frontend dependencies (npm install)...${NC}"
npm install --silent 2>&1 || echo -e "  ${YELLOW}WARNING: npm install encountered issues.${NC}"
echo -e "  ${GREEN}Frontend dependencies ready.${NC}"

echo -e "  ${GRAY}Starting Frontend Dev Server (npm run dev)...${NC}"
npm run dev &
FRONTEND_PID=$!
PIDS+=($FRONTEND_PID)
echo -e "  ${GREEN}Frontend started (PID $FRONTEND_PID).${NC}"

cd "$ROOT_DIR"

# ==================== 5. 就绪信息与监控 ====================
echo -e "\n${CYAN}[Stage 5/5] All services launched!${NC}"
echo -e "${CYAN}===============================================${NC}"
echo -e "  Frontend  : http://localhost:5173"
echo -e "  Backend   : http://localhost:5000"
echo -e "  API Docs  : http://localhost:5000/api/docs"
echo -e "${CYAN}===============================================${NC}"
echo -e "${YELLOW}Tip: Press Ctrl+C to stop all services.${NC}\n"

# 等待所有子进程（Ctrl+C 触发 cleanup）
wait
