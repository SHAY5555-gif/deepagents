# Force restart LangGraph server
Write-Host "Stopping LangGraph server on port 2024..." -ForegroundColor Yellow

$port = 2024
$process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($process) {
    Write-Host "Found process: $process" -ForegroundColor Green
    Stop-Process -Id $process -Force -ErrorAction SilentlyContinue
    Write-Host "Process stopped!" -ForegroundColor Green
} else {
    Write-Host "No process found on port $port" -ForegroundColor Red
}

Write-Host "Waiting 3 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "Starting LangGraph server..." -ForegroundColor Yellow
Set-Location "C:\projects\learn_ten_x_faster\deepagents"
Start-Process -FilePath "C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe" -ArgumentList "dev" -NoNewWindow

Write-Host "Done! Server should be starting..." -ForegroundColor Green
