# Kill all processes using port 2024
$procs = Get-NetTCPConnection -LocalPort 2024 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($procs) {
    foreach ($p in $procs) {
        Write-Host "Stopping process: $p" -ForegroundColor Yellow
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Write-Host "Process $p stopped!" -ForegroundColor Green
    }
} else {
    Write-Host "No processes found using port 2024" -ForegroundColor Red
}
