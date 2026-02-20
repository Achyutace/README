#!/bin/bash

# README PDF Reader - Frontend + Mock Start Script (macOS / Linux)

echo "Starting README PDF Reader Mock Environment..."

# 1. 启动 Mock Server
echo "Starting Mock Server..."
prism mock docs/openapi/openapi.yaml &
MOCK_PID=$!

# 等待一会确保 Mock 服务起来
sleep 2

# 2. 启动前端
echo "Starting Frontend server (Mock mode)..."
cd frontend
npm install
npm run dev:mock &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "Mock Environment is running!"
echo "Frontend: http://localhost:5173"
echo "Mock API: http://127.0.0.1:4010"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop all servers"

# 处理 Ctrl+C
trap "echo 'Stopping servers...'; kill $MOCK_PID $FRONTEND_PID 2>/dev/null; exit" INT

# 等待进程
wait
