# Find process locking langgraph.exe
$file = "C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe"

# Get all processes
$procs = Get-Process | Where-Object { $_.Path -like "*langgraph*" -or $_.ProcessName -like "*langgraph*" -or $_.ProcessName -like "*python*" }

Write-Host "Processes that might be using langgraph.exe:" -ForegroundColor Yellow
$procs | ForEach-Object {
    Write-Host "  Process: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Cyan
    Write-Host "  Path: $($_.Path)" -ForegroundColor Gray
}

# Also check listening ports
Write-Host "`nChecking port 2024..." -ForegroundColor Yellow
$portProcs = Get-NetTCPConnection -LocalPort 2024 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($portProcs) {
    foreach ($pid in $portProcs) {
        if ($pid -gt 0) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Port 2024 used by: $($proc.ProcessName) (PID: $pid)" -ForegroundColor Red
                Write-Host "  Path: $($proc.Path)" -ForegroundColor Gray
            }
        }
    }
}
