# LangGraph CORS Server Starter Script
# =====================================

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Starting LangGraph with CORS Support" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Check if LangGraph is running on port 8123
Write-Host "Checking if LangGraph is running on port 8123..." -ForegroundColor Yellow
$langgraphRunning = Get-NetTCPConnection -LocalPort 8123 -ErrorAction SilentlyContinue

if (-not $langgraphRunning) {
    Write-Host "WARNING: LangGraph does not appear to be running on port 8123" -ForegroundColor Red
    Write-Host "Please run 'langgraph up' first in another terminal" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to continue anyway..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

Write-Host "Starting CORS proxy server on port 8080..." -ForegroundColor Green

# Run the Python server
python langgraph_server_with_cors.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to start the server" -ForegroundColor Red
    Write-Host "Make sure Python and dependencies are installed" -ForegroundColor Yellow
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}