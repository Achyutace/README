# README PDF Reader - Full Stack Start Script (Windows)

Write-Host "Starting README PDF Reader Full Stack Environment..." -ForegroundColor Green

# 1. 检查配置
if (-not (Test-Path "config.yaml")) {
    Write-Host "Warning: config.yaml not found." -ForegroundColor Yellow
    Write-Host "Please copy config.yaml.example to config.yaml and fill in your API keys." -ForegroundColor Yellow
    exit
}

# 2. 清理并创建后端上传目录
$uploadsDir = "backend\uploads"
if (Test-Path $uploadsDir) {
    Remove-Item -Recurse -Force $uploadsDir -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $uploadsDir | Out-Null

# 3. 启动后端服务器
Write-Host "`nStarting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location "$using:PWD\backend"
    
    if (-not (Test-Path "venv")) {
        Write-Host "Creating Python virtual environment..."
        python -m venv venv
    }
    
    & ".\venv\Scripts\activate.ps1"
    Write-Host "Installing backend dependencies..."
    pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    python app.py
}

Start-Sleep -Seconds 2

# 4. 启动前端服务器
Write-Host "Starting frontend server..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:PWD\frontend"
    npm install
    npm run dev
}

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Full Stack Environment is running!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "Backend:  http://localhost:5000" -ForegroundColor White
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""

# 处理 Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # 检查进程
        if ($backendJob.State -eq 'Completed' -or $frontendJob.State -eq 'Completed') {
            Write-Host "One of the servers has stopped." -ForegroundColor Red
            break
        }
    }
}
finally {
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Write-Host "All servers stopped." -ForegroundColor Green
}
