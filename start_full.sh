#!/bin/bash

# README PDF Reader - Full Stack Start Script (macOS / Linux)

echo "Starting README PDF Reader Full Stack Environment..."

# 1. 检查配置
if [ ! -f "config.yaml" ]; then
    echo "Warning: config.yaml not found."
    echo "Please copy config.yaml.example to config.yaml and fill in your API keys."
    exit 1
fi

# 2. 后端：清理上传目录
rm -rf backend/uploads
mkdir -p backend/uploads

# 3. 启动后端
echo "Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment in venv..."
    python3 -m venv venv
fi
source venv/bin/activate
echo "Installing backend dependencies..."
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple

python3 app.py &
BACKEND_PID=$!
cd ..

sleep 2

# 4. 启动前端
echo "Starting frontend server..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "Full Stack Environment is running!"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:5000"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop all servers"

# 处理 Ctrl+C
trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# 等待进程
wait
