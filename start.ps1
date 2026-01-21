# Moonlight PDF Reader - PowerShell Start Script

Write-Host "Starting Moonlight PDF Reader..." -ForegroundColor Green

# 初始化 conda（如果需要）
if (Get-Command conda -ErrorAction SilentlyContinue) {
    # 初始化 conda for PowerShell
    $condaInit = conda info --base
    if ($condaInit) {
        & "$condaInit\Scripts\conda.exe" "shell.powershell" "hook" | Out-String | Invoke-Expression
    }
}

# 启动后端服务器
Write-Host "`nStarting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\backend
    conda activate myenv
    python app.py
}

# 等待后端启动
Start-Sleep -Seconds 2

# 启动前端服务器
Write-Host "Starting frontend server..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\frontend
    npm install
    npm run dev
}

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Moonlight PDF Reader is running!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "Backend:  http://localhost:5000" -ForegroundColor White
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""

# 处理 Ctrl+C
try {
    # 等待用户中断
    while ($true) {
        Start-Sleep -Seconds 1
        
        # 检查进程是否还在运行
        if ($backendJob.State -eq 'Completed' -or $frontendJob.State -eq 'Completed') {
            Write-Host "One of the servers has stopped." -ForegroundColor Red
            break
        }
    }
}
finally {
    # 清理：停止所有作业
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Write-Host "All servers stopped." -ForegroundColor Green
}