# README PDF Reader - Full Stack Start Script (Windows PowerShell)
# 用法: 在项目根目录下运行  .\start_full.ps1

$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "   Starting README PDF Reader Full Stack Core   " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# ==================== 路径定义 ====================
$rootDir     = $PSScriptRoot
$backendDir  = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$venvDir     = Join-Path $backendDir "venv"
$pythonExe   = Join-Path $venvDir "Scripts\python.exe"
$pipExe      = Join-Path $venvDir "Scripts\pip.exe"
$flaskExe    = Join-Path $venvDir "Scripts\flask.exe"
$celeryExe   = Join-Path $venvDir "Scripts\celery.exe"

# 保存所有子进程对象，用于最终清理
$script:childProcesses = @()

# ==================== 清理函数 ====================
function Cleanup {
    Write-Host "`nGracefully stopping all services..." -ForegroundColor Yellow
    foreach ($proc in $script:childProcesses) {
        if ($proc -and -not $proc.HasExited) {
            try {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Host "  Stopped process PID $($proc.Id)" -ForegroundColor Gray
            } catch {
                # 进程可能已自行退出
            }
        }
    }
    # 如果是本脚本启动的 redis-server，也一并关闭
    if ($script:redisStartedByUs) {
        Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "  Stopped redis-server" -ForegroundColor Gray
    }
    Write-Host "All services stopped. Happy coding!" -ForegroundColor Green
}

# ==================== 1. 检查并启动 Redis ====================
Write-Host "`n[Stage 1/5] Checking Redis service..." -ForegroundColor Yellow
$script:redisStartedByUs = $false

$isRedisActive = $false
try {
    $conn = Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet -WarningAction SilentlyContinue
    $isRedisActive = $conn
} catch {}

if ($isRedisActive) {
    Write-Host "  Redis is already running (Port 6379), skipping." -ForegroundColor Green
} else {
    Write-Host "  Redis not detected on port 6379. Searching for binary..." -ForegroundColor Gray
    $redisPath = $null
    $redisCmd = Get-Command "redis-server" -ErrorAction SilentlyContinue
    if ($redisCmd) { $redisPath = $redisCmd.Source }
    if (-not $redisPath) {
        $redisPath = where.exe redis-server 2>$null | Select-Object -First 1
    }

    if ($redisPath) {
        Write-Host "  Found redis-server at: $redisPath" -ForegroundColor Gray
        $redisProc = Start-Process -FilePath $redisPath -WindowStyle Minimized -PassThru
        $script:childProcesses += $redisProc
        $script:redisStartedByUs = $true
        # 等待 Redis 就绪
        Start-Sleep -Seconds 2
        Write-Host "  Redis started (PID $($redisProc.Id))." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: redis-server not found in PATH." -ForegroundColor Red
        Write-Host "  Please start Redis manually or add it to your PATH." -ForegroundColor Yellow
    }
}

# ==================== 2. 后端环境准备 ====================
Write-Host "`n[Stage 2/5] Preparing backend environment..." -ForegroundColor Yellow

# 2a. 创建虚拟环境（如不存在）
if (-not (Test-Path $pythonExe)) {
    Write-Host "  Virtual environment not found. Creating with Python 3.12..." -ForegroundColor Gray
    try {
        $pyVersion = & py -3.12 --version 2>&1
        Write-Host "  Detected: $pyVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Python 3.12 not found via 'py -3.12'." -ForegroundColor Red
        Write-Host "  Install Python 3.12 from https://www.python.org/downloads/" -ForegroundColor Gray
        exit 1
    }
    & py -3.12 -m venv $venvDir
    if (-not (Test-Path $pythonExe)) {
        Write-Host "  ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Virtual environment created." -ForegroundColor Green
}

# 2b. 安装 Python 依赖
Write-Host "  Installing Python dependencies..." -ForegroundColor Gray
& $pipExe install -r (Join-Path $backendDir "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Dependencies ready." -ForegroundColor Green

# 2c. 数据库迁移（需要在 backend 目录下执行）
Write-Host "  Syncing database schema (flask db upgrade)..." -ForegroundColor Gray
Push-Location $backendDir
try {
    $env:FLASK_APP = "app.py"
    & $flaskExe db upgrade 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Database sync successful." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Database sync returned non-zero exit code." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  WARNING: Database sync failed: $_" -ForegroundColor Yellow
}
Pop-Location

# ==================== 3. 启动后端服务 ====================
Write-Host "`n[Stage 3/5] Starting backend services..." -ForegroundColor Yellow

# 3a. 启动 Backend API  —— 使用 Start-Process 在独立窗口中运行
Write-Host "  Starting Backend API (python app.py)..." -ForegroundColor Gray
$apiProc = Start-Process -FilePath $pythonExe `
    -ArgumentList "app.py" `
    -WorkingDirectory $backendDir `
    -PassThru `
    -NoNewWindow
$script:childProcesses += $apiProc
Write-Host "  Backend API started (PID $($apiProc.Id))." -ForegroundColor Green

# 短暂等待，检查是否立即崩溃
Start-Sleep -Seconds 3
if ($apiProc.HasExited) {
    Write-Host "  ERROR: Backend API exited immediately with code $($apiProc.ExitCode)." -ForegroundColor Red
    Write-Host "  Please check the output above or run 'cd backend && python app.py' manually to see errors." -ForegroundColor Yellow
    Cleanup
    exit 1
}

# 3b. 启动 Celery Worker
Write-Host "  Starting Celery Worker..." -ForegroundColor Gray
$celeryProc = Start-Process -FilePath $celeryExe `
    -ArgumentList "-A celery_app worker --loglevel=info --pool=solo" `
    -WorkingDirectory $backendDir `
    -PassThru `
    -NoNewWindow
$script:childProcesses += $celeryProc
Write-Host "  Celery Worker started (PID $($celeryProc.Id))." -ForegroundColor Green

# ==================== 4. 启动前端服务 ====================
Write-Host "`n[Stage 4/5] Starting frontend service..." -ForegroundColor Yellow

# 4a. npm install
Write-Host "  Checking frontend dependencies (npm install)..." -ForegroundColor Gray
Push-Location $frontendDir
try {
    npm install --silent 2>&1 | Out-Null
    Write-Host "  Frontend dependencies ready." -ForegroundColor Green
} catch {
    Write-Host "  WARNING: npm install encountered issues." -ForegroundColor Yellow
}
Pop-Location

# 4b. 启动前端 dev server
Write-Host "  Starting Frontend Dev Server (npm run dev)..." -ForegroundColor Gray
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory $frontendDir `
    -PassThru `
    -NoNewWindow
$script:childProcesses += $frontendProc
Write-Host "  Frontend started (PID $($frontendProc.Id))." -ForegroundColor Green

# ==================== 5. 就绪信息与监控 ====================
Write-Host "`n[Stage 5/5] All services launched!" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Frontend  : http://localhost:5173" -ForegroundColor White
Write-Host "  Backend   : http://localhost:5000" -ForegroundColor White
Write-Host "  API Docs  : http://localhost:5000/api/docs" -ForegroundColor White
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Tip: Press Ctrl+C to stop all services.`n" -ForegroundColor Yellow

# 持续监控，按 Ctrl+C 退出
try {
    while ($true) {
        Start-Sleep -Seconds 3

        if ($apiProc.HasExited) {
            Write-Host "[WARNING] Backend API process has exited (Code: $($apiProc.ExitCode))." -ForegroundColor Red
            break
        }
        if ($celeryProc.HasExited) {
            Write-Host "[WARNING] Celery Worker process has exited (Code: $($celeryProc.ExitCode))." -ForegroundColor Red
            break
        }
    }
} finally {
    Cleanup
}
