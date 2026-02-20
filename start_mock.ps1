# README PDF Reader - Frontend + Mock Start Script (Windows)

Write-Host "Starting README PDF Reader Mock Environment..." -ForegroundColor Green

# 1. 启动 Mock 服务
Write-Host "`nStarting Mock Server..." -ForegroundColor Yellow
$mockJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    prism mock docs/openapi/openapi.yaml
}

Start-Sleep -Seconds 2

# 2. 启动前端服务
Write-Host "Starting Frontend Server (Mock mode)..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:PWD\frontend"
    npm install
    npm run dev:mock
}

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Mock Environment is running!" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "Mock API: http://127.0.0.1:4010" -ForegroundColor White
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers" -ForegroundColor Yellow
Write-Host ""

# 处理 Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # 检查进程
        if ($mockJob.State -eq 'Completed' -or $frontendJob.State -eq 'Completed') {
            Write-Host "One of the servers has stopped." -ForegroundColor Red
            break
        }
    }
}
finally {
    Write-Host "`nStopping servers..." -ForegroundColor Yellow
    Stop-Job -Job $mockJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $mockJob, $frontendJob -ErrorAction SilentlyContinue
    Write-Host "All servers stopped." -ForegroundColor Green
}
